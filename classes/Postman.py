# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the Postman class, which handles inter-object messages
# and logging. Try not to touch this :)
# ---------------------------------------------------------------------------

import signal
import sys
import time
import traceback
#from Queue import *
from exceptions import SystemExit

# ---------------------------------------------------------------------------

from classes.Common import *
from classes.Constants import *

#from Plugins import *

from classes.ChatterGizmo import ChatterGizmo
from classes.DataMonkey import DataMonkey
from classes.HTTPMonster import HTTPMonster
from classes.PluginHandler import PluginHandler
from classes.Plugin import Plugin
from classes.TimeKeeper import TimeKeeper
from classes.Helper import Helper

# ---------------------------------------------------------------------------

class Postman:
	def __init__(self, ConfigFile, Config):
		self.ConfigFile = ConfigFile
		self.Config = Config
		
		self.__Stopping = 0
		
		self.__Setup_From_Config()

		# Install our signal handlers here
		# note, win32 has no SIGHUP signal
		if hasattr(signal, 'SIGHUP'):
			signal.signal(signal.SIGHUP, self.SIG_HUP)
		signal.signal(signal.SIGTERM, self.SIG_TERM)
		
		
		# Open our log file and rotate it if we have to
		self.__Log_Open()
		self.__Log_Rotate()

		# Initialise the global message queue
		self.inQueue = []
		
		# Load all the configs supplied for plugins
		self.__Load_Configs()
		
		
		# Create our children
		self.__Children = {}
		
		system = [ TimeKeeper, PluginHandler, ChatterGizmo, DataMonkey, HTTPMonster, Helper ]
		for cls in system:
			tolog = "Starting system object '%s'" % cls.__name__
			self.__Log(LOG_ALWAYS, tolog)
			
			instance = cls(cls.__name__, self.inQueue, self.Config)
			self.__Children[cls.__name__] = instance
		
		for name in self.__plugin_list:
			self.__import_plugin(name)

		# add Helper to the list of plugins so that it can do its thing
		self.__plugin_list.append('Helper')

	# -----------------------------------------------------------------------

	def __Setup_From_Config(self):
		self.__logfile_filename = self.Config.get('logging', 'log_file')
		self.__log_debug = self.Config.getboolean('logging', 'debug')
		self.__log_debug_msg = self.Config.getboolean('logging', 'debug_msg')
		self.__plugin_list = self.Config.get('plugin', 'plugins').split()

	# -----------------------------------------------------------------------

	def __import_plugin(self, name):
		#plugins = self.__Children['PluginHandler'].pluginList()
		#for clsname in plugins:
		#	tolog = "Starting plugin object '%s'" % clsname
		#	self.__Log(LOG_DEBUG, tolog)
		#	
		#	cls = globals()[clsname]
		#	instance = cls(cls.__name__, self.inQueue, self.Config)
		#	self.__Children[cls.__name__] = instance

		try:
			module = __import__('plugins.%s' % name, globals(), locals(), [name])
			globals()[name] = getattr(module, name)
		except ImportError:
			tolog = "No such plugin: %s" % name
			self.__Log(LOG_WARNING, tolog)
		else:
			tolog = "Starting plugin object '%s'" % name
			self.__Log(LOG_ALWAYS, tolog)
			
			cls = globals()[name]
			instance = cls(cls.__name__, self.inQueue, self.Config)
			self.__Children[cls.__name__] = instance
	
	# -----------------------------------------------------------------------
	
	def SIG_HUP(self, signum, frame):
		self.__Log(LOG_WARNING, 'Received SIGHUP')
		self.__Reload_Config()
	
	def SIG_TERM(self, signum, frame):
		self.__Log(LOG_WARNING, 'Received SIGTERM')
		self.__Shutdown('Terminated!')
	
	# -----------------------------------------------------------------------
	
	def run_forever(self):
		_sleep = time.sleep
		_time = time.time
		
		sometimes_counter = 0
		
		for child in self.__Children.values():
			if hasattr(child, 'run_once'):
				child.run_once()
		
		while 1:
			try:
				#if not self.inQueue.empty():
				if self.inQueue:
					#message = self.inQueue.get(0)
					message = self.inQueue.pop(0)
					
					# If it's targeted at us, process it
					if message.targets == ['Postman']:
						if message.ident == REQ_LOG:
							self.__Log(*message.data)
						
						# Reload our config
						elif message.ident == REQ_LOAD_CONFIG:
							self.__Reload_Config()
							
							#self.sendMessage('HeadHoncho', REPLY_LOAD_CONFIG, message.data)
						
						elif message.ident == REQ_SHUTDOWN:
							self.__Shutdown(message.data[0])
						
						# A child just shut itself down. If it was a plugin,
						# "unimport" it.
						elif message.ident == REPLY_SHUTDOWN:
							if issubclass(globals()[message.source], Plugin):
								del self.__Children[message.source]
								del globals()[message.source]
					
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
				
				
				# Check for messages, and run any _always loops
				children = self.__Children.values()
				
				for child in children:
					child.handleMessages()
					
					if hasattr(child, 'run_always'):
						child.run_always()
				
				
				# Do things that don't need to be done all that often
				sometimes_counter += 1
				if sometimes_counter == 4:
					sometimes_counter = 0
					
					# See if our log file has to rotate
					self.__Log_Rotate()
					
					# If we're shutting down, see if all of our children have
					# stopped.
					if self.__Stopping == 1:
						self.__Shutdown_Check()
					
					# Run anything our children want done occasionally
					currtime = _time()
					
					for child in children:
						if hasattr(child, 'run_sometimes'):
							child.run_sometimes(currtime)
				
				# Sleep for a while
				_sleep(0.05)
			
			except KeyboardInterrupt:
				self.__Shutdown('Ctrl-C pressed')
			
			except:
				trace = sys.exc_info()
				
				# If it's a SystemExit, we're really meant to be stopping now
				if trace[0] == SystemExit:
					raise
				
				self.__Log(LOG_ALWAYS, '*******************************************************')
				
				self.__Log(LOG_ALWAYS, 'Traceback (most recent call last):')
				
				for entry in traceback.extract_tb(trace[2]):
					tolog = '  File "%s", line %d, in %s' % entry[:-1]
					self.__Log(LOG_ALWAYS, tolog)
					tolog = '    %s' % entry[-1]
					self.__Log(LOG_ALWAYS, tolog)
				
				for line in traceback.format_exception_only(trace[0], trace[1]):
					tolog = line.replace('\n', '')
					self.__Log(LOG_ALWAYS, tolog)
				
				self.__Log(LOG_ALWAYS, '*******************************************************')
				
				# We crashed during shutdown? Not Good.
				if self.__Stopping == 1:
					self.__Log(LOG_ALWAYS, "Exception during shutdown, I'm outta here.")
					sys.exit(-1)
				
				else:
					self.__Shutdown('Crashed!')
	
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
			
			sys.exit(1)
		
		elif alive:
			tolog = 'Objects still alive: %s' % ', '.join(alive)
			self.__Log(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	
	def __Log_Open(self):
		try:
			self.__logfile = open(self.__logfile_filename, 'a+')
		
		except:
			print "Failed to open our log file!"
			sys.exit(-1)
		
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
	
	# -----------------------------------------------------------------------
	# Read the first line of our current log file. If it's date is older than
	# our current date, rotate it and start a new one.
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
		
		print timeshort, text
		
		tolog = '%s %s\n' % (timelong, text)
		self.__logfile.write(tolog)
		self.__logfile.flush()
	
	# -----------------------------------------------------------------------
	
	# Load config info
	def __Load_Configs(self):
		config_dir = self.Config.get('plugin', 'config_dir')
		if os.path.exists(config_dir):
			for config_file in os.listdir(config_dir):
				if config_file.endswith(".conf"):
					self.Config.read(os.path.join(config_dir, config_file))
	
	# Reload our config, duh
	def __Reload_Config(self):
		self.__Log(LOG_ALWAYS, 'Rehashing config...')
		
		# Delete all of our old sections first
		for section in self.Config.sections():
			junk = self.Config.remove_section(section)
		
		old_plugin_list = self.__plugin_list
		self.Config.read(self.ConfigFile)
		self.__Setup_From_Config()
		self.__Load_Configs()
		
		# re-add Helper to the plugin list, since it will have been clobbered
		self.__plugin_list.append('Helper')
		
		# Check if any plugins have been removed from the config.
		# If so, shut them down
		for plugin_name in old_plugin_list:
			if plugin_name not in self.__plugin_list:
				self.sendMessage(plugin_name, REQ_SHUTDOWN, None)
		
		# Check for any new plugins that have been added to the list
		for plugin_name in self.__plugin_list:
			if plugin_name not in old_plugin_list:
				self.__import_plugin(plugin_name)
				if hasattr(self.__Children[plugin_name], 'run_once'):
					self.__Children[plugin_name].run_once()
		
		# This is where you'd expect the code to remove any imported plugins
		# that are no longer needed to go, but instead we put it in the handler
		# for the REPLY_SHUTDOWN message we get.
		
		# Tell everyone we reloaded
		self.sendMessage(None, REQ_REHASH, None)
	

# ---------------------------------------------------------------------------
