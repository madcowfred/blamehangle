# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
This is the main loop of blamehangle, which handles inter-object messages and
logging. Don't mess with it.
"""

import asyncore
import os
import select
import signal
import smtplib
import sys
import time
import traceback
from exceptions import SystemExit

# ---------------------------------------------------------------------------

from classes.Constants import *
from classes.Message import Message
from classes.Plugin import Plugin
from classes.Users import *

from classes.make_constants import _make_constants

from classes.ChatterGizmo import ChatterGizmo
from classes.DataMonkey import DataMonkey
from classes.HTTPMonster import HTTPMonster
from classes.PluginHandler import PluginHandler
from classes.Resolver import Resolver

# ---------------------------------------------------------------------------

MAIL_TEXT =  "This is an automatic e-mail message from blamehangle. You are receiving this because "
MAIL_TEXT += "someone has you listed in their mail/tracebacks setting."

# ---------------------------------------------------------------------------

class Postman:
	def __init__(self, ConfigFile, Config):
		self.ConfigFile = ConfigFile
		self.Config = Config
		self.Userlist = {}
		
		# Initialise the global message queue
		self.inQueue = []
		
		# mtimes for plugins
		self.__mtimes = {}
		# these plugins really want to be reloaded
		self.__reloadme = {}
		# lists of methods to run always/sometimes
		self.__run_always = []
		self.__run_sometimes = []
		
		self.__Started = time.time()
		self.__Stopping = 0
		
		# We can't recreate this all the time or children lose the reference
		self.Userlist = HangleUserList(self)
		
		# Install our signal handlers here
		# note, win32 has no SIGHUP signal
		if hasattr(signal, 'SIGHUP'):
			signal.signal(signal.SIGHUP, self.SIG_HUP)
		signal.signal(signal.SIGTERM, self.SIG_TERM)
		
		# ?
		self.__Setup_From_Config()
		
		# Load all the configs supplied for plugins
		self.__Load_Configs()
		
		# Open our log file and rotate it if we have to
		self.__Log_Open()
		self.__Log_Rotate()
		
		
		# Create a poll object for async bits to use. If the user doesn't have
		# poll, we're going to have to fake it.
		try:
			asyncore.poller = select.poll()
		except AttributeError:
			from classes.FakePoll import FakePoll
			asyncore.poller = FakePoll()
		
		# Create our children
		self.__Children = {}
		
		system = [ PluginHandler, Resolver, ChatterGizmo, DataMonkey, HTTPMonster ]
		for cls in system:
			tolog = "Starting system object '%s'" % cls.__name__
			self.__Log(LOG_ALWAYS, tolog)
			
			instance = cls(cls.__name__, self.inQueue, self.Config, self.Userlist)
			self.__Children[cls.__name__] = instance
			
			if hasattr(instance, 'run_always'):
				self.__run_always.append(instance.run_always)
			if hasattr(instance, 'run_sometimes'):
				self.__run_sometimes.append(instance.run_sometimes)
		
		# Import plugins
		for name in self.__plugin_list:
			self.__Plugin_Load(name)
	
	# -----------------------------------------------------------------------
	
	def __Setup_From_Config(self):
		self.__logfile_filename = self.Config.get('logging', 'log_file')
		self.__log_debug = self.Config.getboolean('logging', 'debug')
		self.__log_debug_msg = self.Config.getboolean('logging', 'debug_msg')
		self.__log_debug_query = self.Config.getboolean('logging', 'debug_query')
		
		self.__plugin_list = self.Config.get('plugin', 'plugins').split()
		
		self.__mail_server = self.Config.get('mail', 'server')
		self.__mail_from = self.Config.get('mail', 'from')
		self.__mail_tracebacks = self.Config.get('mail', 'tracebacks').split()
	
	# -----------------------------------------------------------------------
	# Load a plugin
	def __Plugin_Load(self, name, runonce=0):
		# Try to import
		try:
			module = __import__('plugins.' + name, globals(), locals(), [name])
			globals()[name] = getattr(module, name)
		
		except ImportError:
			tolog = "No such plugin '%s'" % name
			self.__Log(LOG_WARNING, tolog)
		
		except:
			self.__Log_Exception(dontcrash=1)
			self.__Plugin_Unload(name)
		
		else:
			# Start it up
			tolog = "Starting plugin object '%s'" % name
			self.__Log(LOG_ALWAYS, tolog)
			
			try:
				cls = globals()[name]
				instance = cls(cls.__name__, self.inQueue, self.Config, self.Userlist)
				
				if runonce and hasattr(instance, 'run_once'):
					instance.run_once()
			
			except:
				self.__Log_Exception(dontcrash=1)
				self.__Plugin_Unload(name)
			
			else:
				pluginpath = '%s.py' % os.path.join('plugins', name)
				self.__mtimes[name] = os.stat(pluginpath).st_mtime
				
				self.__Children[cls.__name__] = instance
				
				if hasattr(instance, 'run_always'):
					self.__run_always.append(instance.run_always)
				if hasattr(instance, 'run_sometimes'):
					self.__run_sometimes.append(instance.run_sometimes)
	
	# Unload a plugin, making sure we unload the module too
	def __Plugin_Unload(self, name):
		#tolog = "Unloading plugin object '%s'" % name
		#self.__Log(LOG_DEBUG, tolog)
		
		if self.__Children.has_key(name):
			# Remove them from the run_* lists
			child = self.__Children[name]
			if hasattr(child, 'run_always'):
				for meth in self.__run_always:
					if meth == child.run_always:
						self.__run_always.remove(meth)
						break
			if hasattr(child, 'run_sometimes'):
				for meth in self.__run_sometimes:
					if meth == child.run_sometimes:
						self.__run_sometimes.remove(meth)
						break
			
			del self.__Children[name]
		
		# 'unload' the module
		if globals().has_key(name):
			del globals()[name]
		
		try:
			del sys.modules['plugins.' + name]
		except KeyError:
			pass
		
		# Tell PluginHandler that we unloaded them
		self.sendMessage('PluginHandler', PLUGIN_DIED, name)
	
	# -----------------------------------------------------------------------
	
	def SIG_HUP(self, signum, frame):
		self.__Log(LOG_WARNING, 'Received SIGHUP')
		self.__Reload_Config()
	
	def SIG_TERM(self, signum, frame):
		self.__Log(LOG_WARNING, 'Received SIGTERM')
		self.__Shutdown('Terminated!')
	
	# -----------------------------------------------------------------------
	
	def run_forever(self):
		sometimes_counter = 0
		
		# Run any run_once methods that children have
		for child in self.__Children.values():
			if hasattr(child, 'run_once'):
				child.run_once()
		
		while 1:
			try:
				while self.inQueue:
					message = self.inQueue.pop(0)
					
					# If it's targeted at us, process it
					if message.targets == ['Postman']:
						if message.ident == REQ_LOG:
							self.__Log(*message.data)
						
						# Reload our config
						elif message.ident == REQ_LOAD_CONFIG:
							self.__Reload_Config()
						
						# Die!
						elif message.ident == REQ_SHUTDOWN:
							self.__Shutdown(message.data[0])
						
						# Someone wants some stats
						elif message.ident == GATHER_STATS:
							message.data['plugins'] = len([v for v in self.__Children.values() if isinstance(v, Plugin)])
							message.data['started'] = self.__Started
							self.sendMessage('BotStatus', GATHER_STATS, message.data)
						
						# A child just shut itself down. If it was a plugin,
						# "unimport" it.
						elif message.ident == REPLY_SHUTDOWN:
							child = message.source
							try:
								if issubclass(globals()[child], Plugin):
									self.__Plugin_Unload(child)
									
									# If it's really being reloaded, do that
									if self.__reloadme.has_key(child):
										del self.__reloadme[child]
										self.__Plugin_Load(child, runonce=1)
										
										# If reloadme is empty, rehash now
										if not self.__reloadme:
											self.sendMessage(None, REQ_REHASH, None)
							
							except KeyError:
								tolog = "Postman received a message from '%s', but it's dead!" % (child)
								self.__Log(LOG_WARNING, tolog)
					
					else:
						# Log the message if debug is enabled
						self.__Log(LOG_MSG, message)
						
						# If it's a global message, send it to everyone
						if message.targetstring == 'ALL':
							for child in self.__Children.values():
								child.inQueue.append(message)
						
						# If it's not, send it to each thread listed in targets
						else:
							for name in message.targets:
								if name in self.__Children:
									self.__Children[name].inQueue.append(message)
								else:
									tolog = "invalid target for Message ('%s') : %s" % (name, message)
									self.__Log(LOG_WARNING, tolog)
				
				
				# Deliver any waiting messages to children
				for name, child in self.__Children.items():
					if not child.inQueue:
						continue
					
					message = child.inQueue.pop(0)
					
					methname = '_message_%s' % message.ident
					if hasattr(child, methname):
						getattr(child, methname)(message)
					else:
						tolog = 'Unhandled message in %s: %s' % (name, message.ident)
						self.__Log(LOG_DEBUG, tolog)
				
				
				# Poll our sockets
				results = asyncore.poller.poll(0)
				for fd, event in results:
					obj = asyncore.socket_map.get(fd)
					if obj is None:
						tolog = 'Invalid FD for poll()? %d' % fd
						self.__Log(LOG_WARNING, tolog)
						continue
					
					if event & select.POLLIN:
						asyncore.read(obj)
					elif event & select.POLLOUT:
						asyncore.write(obj)
					elif event & select.POLLNVAL:
						tolog = "FD %d is still in the poll, but it's closed!" % fd
						self.__Log(LOG_WARNING, tolog)
					else:
						tolog = 'Bizarre poll response! %d: %d' % (fd, event)
						self.__Log(LOG_WARNING, tolog)
				
				
				# Run any always loops
				for meth in self.__run_always:
					meth()
				
				# Do things that don't need to be done all that often
				sometimes_counter = (sometimes_counter + 1) % 4
				if sometimes_counter == 0:
					#currtime = _time()
					currtime = time.time()
					
					# See if our log file has to rotate
					if currtime >= self.__rotate_after:
						self.__Log_Rotate()
					
					# If we're shutting down, see if all of our children have
					# stopped.
					if self.__Stopping == 1 and self.__Shutdown_Check():
						return
					
					# Run anything our children want done occasionally
					for meth in self.__run_sometimes:
						meth(currtime)
				
				# Sleep for a while
				time.sleep(0.05)
			
			except KeyboardInterrupt:
				self.__Shutdown('Ctrl-C pressed')
			
			except:
				self.__Log_Exception()
	
	# Use the magical constants binder to speed things up
	run_forever = _make_constants(run_forever)
	
	#------------------------------------------------------------------------
	# Our own mangled version of sendMessage
	#------------------------------------------------------------------------
	def sendMessage(self, *args):
		message = Message('Postman', *args)
		
		# Log the message if debug is enabled
		self.__Log(LOG_MSG, message)
		
		if message.targets:
			for name in message.targets:
				if name in self.__Children:
					self.__Children[name].inQueue.append(message)
				else:
					tolog = "WARNING: invalid target for Message ('%s')" % name
					self.__Log(LOG_ALWAYS, tolog)
		
		else:
			for child in self.__Children.values():
				child.inQueue.append(message)
	
	#------------------------------------------------------------------------
	# Initiates a shutdown of our children, and ourselves.
	#------------------------------------------------------------------------
	def __Shutdown(self, why):
		# If we're already shutting down, return
		if self.__Stopping:
			return
		
		self.__Stopping = 1
		self.__Shutdown_Start = time.time()
		
		tolog = 'Shutting down (%s)...' % why
		self.__Log(LOG_ALWAYS, tolog)
		
		# Send shutdown messages to everyone
		self.sendMessage(None, REQ_SHUTDOWN, why)
	
	# Don't actually quit until our children have finished shutting down
	def __Shutdown_Check(self):
		alive = [name for name, child in self.__Children.items() if child.stopnow == 0]
		
		# If our children are asleep, and we have no messages, die
		if not alive and not self.inQueue:
			self.__Log(LOG_ALWAYS, 'Shutdown complete')
			return 1
		
		elif alive:
			# If we've been shutting down for a while, just give up
			if time.time() - self.__Shutdown_Start >= 10:
				tolog = 'Shutdown timeout expired: %s' % ', '.join(alive)
				self.__Log(LOG_ALWAYS, tolog)
				return 1
			
			else:
				tolog = 'Objects still alive: %s' % ', '.join(alive)
				self.__Log(LOG_DEBUG, tolog)
				return 0
		
		return 0
	
	# -----------------------------------------------------------------------
	# Open our log file and work out what time we should start thinking about
	# rotating it.
	# -----------------------------------------------------------------------
	def __Log_Open(self):
		try:
			self.__logfile = open(self.__logfile_filename, 'a+')
		
		except Exception, msg:
			print "Failed to open our log file: %s" % (msg)
			sys.exit(1)
		
		else:
			if self.__logfile.tell() > 0:
				self.__logfile.seek(0, 0)
				
				firstline = self.__logfile.readline()
				if firstline:
					self.__logdate = firstline[0:10]
					self.__logfile.seek(0, 2)
				
				else:
					self.__logdate = time.strftime("%Y/%m/%d")
			
			else:
				self.__logdate = time.strftime("%Y/%m/%d")
			
			# Scary :|
			t = time.localtime()
			t2 = (t[0], t[1], t[2], 23, 59, 55, t[6], t[7], t[8])
			self.__rotate_after = time.mktime(t2)
	
	# -----------------------------------------------------------------------
	# See if it's time to rotate our log file yet.
	# -----------------------------------------------------------------------
	def __Log_Rotate(self):
		today = time.strftime("%Y/%m/%d")
		
		if self.__logdate != today:
			self.__logfile.close()
			
			newname = '%s-%s' % (self.__logfile_filename, self.__logdate.replace('/', ''))
			os.rename(self.__logfile_filename, newname)
			
			ld = self.__logdate
			
			self.__Log_Open()
			
			tolog = 'Rotated log file for %s' % ld
			self.__Log(LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Log a line to our log file.
	# -----------------------------------------------------------------------
	def __Log(self, level, text):
		currtime = time.localtime()
		timeshort = time.strftime("[%H:%M:%S]", currtime)
		timelong = time.strftime("%Y/%m/%d %H:%M:%S", currtime)
		
		if level == LOG_WARNING:
			text = 'WARNING: %s' % text
		
		elif level == LOG_DEBUG:
			if not self.__log_debug:
				return
			text = '[DEBUG] %s' % text
		
		elif level == LOG_MSG:
			if not self.__log_debug_msg:
				return
			text = '[DEBUG] %s' % text
		
		elif level == LOG_QUERY:
			if not self.__log_debug_query:
				return
			text = '[QUERY] %s' % text
		
		print timeshort, text
		
		tolog = '%s %s\n' % (timelong, text)
		self.__logfile.write(tolog)
		self.__logfile.flush()
	
	# -----------------------------------------------------------------------
	# Log an exception nicely
	def __Log_Exception(self, dontcrash=0):
		_type, _value, _tb = sys.exc_info()
		
		# If it's a SystemExit exception, we're really meant to die now
		if _type == SystemExit:
			raise
		
		# Extract then delete, to avoid a circular reference thing
		entries = traceback.extract_tb(_tb)
		del _tb
		
		# Log these lines
		logme = []
		
		# Remember the last filename
		last_file = ''
		
		logme.append('*******************************************************')
		
		logme.append('Traceback (most recent call last):')
		
		for entry in entries:
			last_file = entry[:-1][0]
			tolog = '  File "%s", line %d, in %s' % entry[:-1]
			logme.append(tolog)
			tolog = '    %s' % entry[-1]
			logme.append(tolog)
		
		for line in traceback.format_exception_only(_type, _value):
			tolog = line.replace('\n', '')
			logme.append(tolog)
		
		logme.append('*******************************************************')
		
		# Log all that stuff now
		for line in logme:
			self.__Log(LOG_ALWAYS, line)
		
		# Maybe e-mail our bosses
		if self.__mail_tracebacks:
			lines = []
			
			line = 'From: %s' % self.__mail_from
			lines.append(line)
			
			mailto = ', '.join(self.__mail_tracebacks)
			line = 'To: %s' % mailto
			lines.append(line)
			
			line = 'Subject: blamehangle error message'
			lines.append(line)
			
			line = 'X-Mailer: blamehangle Postman'
			lines.append(line)
			
			lines.append('')
			lines.append(MAIL_TEXT)
			lines.append('')
			lines.extend(logme)
			
			# Send it!
			message = '\r\n'.join(lines)
			
			try:
				server = smtplib.SMTP(self.__mail_server)
				server.sendmail(self.__mail_from, self.__mail_tracebacks, message)
				server.quit()
			
			except Exception, msg:
				tolog = 'Error sending mail: %s' % msg
				self.__Log(LOG_WARNING, tolog)
			
			else:
				tolog = 'Sent error mail to: %s' % mailto
				self.__Log(LOG_ALWAYS, tolog)
		
		# We crashed during shutdown? Not Good.
		if self.__Stopping == 1:
			self.__Log(LOG_ALWAYS, "Exception during shutdown, I'm outta here.")
			sys.exit(1)
		
		else:
			# Was it a plugin? If so, we can try shutting it down
			head, tail = os.path.split(last_file)
			if head.endswith('plugins'):
				root, ext = os.path.splitext(tail)
				if root in self.__Children:
					self.sendMessage(root, REQ_SHUTDOWN, None)
			
			# If we're supposed to crash, do that
			elif not dontcrash:
				self.__Shutdown('Crashed!')
	
	# -----------------------------------------------------------------------
	# Load config info
	def __Load_Configs(self):
		config_dir = self.Config.get('plugin', 'config_dir')
		if os.path.exists(config_dir):
			for config_file in os.listdir(config_dir):
				if config_file.endswith(".conf"):
					self.Config.read(os.path.join(config_dir, config_file))
		
		# Set up the userlist now
		self.Userlist.Reload()
	
	# Reload our config, duh
	def __Reload_Config(self):
		self.__Log(LOG_ALWAYS, 'Rehashing config...')
		
		# Make a copy of the plugin list
		old_plugin_list = self.__plugin_list[:]
		
		# Delete all of our old sections first
		for section in self.Config.sections():
			junk = self.Config.remove_section(section)
		
		# Re-load the configs
		self.Config.read(self.ConfigFile)
		self.__Setup_From_Config()
		self.__Load_Configs()
		
		# Check if any plugins have been removed from the config. If so, try
		# and shut them down.
		for plugin_name in old_plugin_list:
			if plugin_name not in self.__plugin_list:
				if plugin_name in self.__Children:
					self.sendMessage(plugin_name, REQ_SHUTDOWN, None)
		
		# Check for any new plugins that have been added to the list
		for plugin_name in self.__plugin_list:
			# New plugin, or plugin that crashed while loading
			if plugin_name not in old_plugin_list or plugin_name not in self.__Children:
				self.__Plugin_Load(plugin_name, runonce=1)
			# If it's already loaded, check the mtime and possibly reload
			else:
				pluginpath = '%s.py' % os.path.join('plugins', plugin_name)
				if os.path.exists(pluginpath):
					newmtime = os.stat(pluginpath).st_mtime
					
					if newmtime > self.__mtimes[plugin_name]:
						self.__mtimes[plugin_name] = newmtime
						self.__reloadme[plugin_name] = 1
						
						tolog = "Plugin '%s' has been updated, reloading" % plugin_name
						self.__Log(LOG_ALWAYS, tolog)
						
						self.sendMessage(plugin_name, REQ_SHUTDOWN, None)
		
		# This is where you'd expect the code to remove any imported plugins
		# that are no longer needed to go, but instead we put it in the handler
		# for the REPLY_SHUTDOWN message we get.
		
		# If no plugins are being reloaded, tell everyone that we have reloaded.
		# Otherwise, we can do that once it's loaded itself :|
		if not self.__reloadme:
			self.sendMessage(None, REQ_REHASH, None)
