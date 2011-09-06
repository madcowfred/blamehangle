# Copyright (c) 2003-2009, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
This is the main loop of blamehangle, which handles inter-object message
passing, the main asyncore poll() loop, logging and several other important
things. Don't mess with it.
"""

import asyncore
import logging
import logging.handlers
import os
import select
import signal
import sys
import time
import traceback

from exceptions import SystemExit

# ---------------------------------------------------------------------------

from classes.Constants import *
from classes.Message import Message
from classes.Plugin import Plugin
from classes.Users import *

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
		
		# Load all the configs supplied for plugins
		self.__Load_Configs()
		
		# Initialise our logging
		self.__Log_Init()
		
		
		# Create a poll object for async bits to use. If the user doesn't have
		# poll, we're going to have to fake it.
		try:
			asyncore.poller = select.poll()
			self.logger.info('Using poll() for sockets')
		except AttributeError:
			from classes.FakePoll import FakePoll
			asyncore.poller = FakePoll()
			self.logger.info('Using FakePoll() for sockets')
		
		# Create our children
		self.__Children = {}
		
		system = [ PluginHandler, Resolver, ChatterGizmo, DataMonkey, HTTPMonster ]
		for cls in system:
			tolog = "Starting system object '%s'" % (cls.__name__)
			self.logger.info(tolog)
			
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
	# Load a plugin
	def __Plugin_Load(self, name, runonce=0):
		# Try to import
		try:
			module = __import__('plugins.' + name, globals(), locals(), [name])
			globals()[name] = getattr(module, name)
		
		except ImportError, msg:
			tolog = "Error while importing plugin '%s': %s" % (name, msg)
			self.logger.warn(tolog)
			self.__Plugin_Unload(name)
		
		except:
			self.__Log_Exception(dontcrash=1)
			self.__Plugin_Unload(name)
		
		else:
			# Start it up
			tolog = "Starting plugin object '%s'" % (name)
			self.logger.info(tolog)
			
			try:
				cls = globals()[name]
				instance = cls(cls.__name__, self.inQueue, self.Config, self.Userlist)
				
				if runonce and hasattr(instance, 'run_once'):
					instance.run_once()
			
			except:
				self.__Log_Exception(dontcrash=1)
				self.__Plugin_Unload(name)
			
			else:
				pluginpath = '%s.py' % (os.path.join('plugins', name))
				self.__mtimes[name] = os.stat(pluginpath).st_mtime
				
				self.__Children[cls.__name__] = instance
				
				if hasattr(instance, 'run_always'):
					self.__run_always.append(instance.run_always)
				if hasattr(instance, 'run_sometimes'):
					self.__run_sometimes.append(instance.run_sometimes)
	
	# Unload a plugin, making sure we unload the module too
	def __Plugin_Unload(self, name):
		tolog = "Unloading plugin object '%s'" % (name)
		self.logger.info(tolog)
		
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
		
		# Remove the global name bound to the module
		try:
			del globals()[name]
		except KeyError:
			pass
		
		# Remove the module from memory
		try:
			del sys.modules['plugins.' + name]
		except KeyError:
			pass
		
		# Tell PluginHandler that we unloaded them
		self.sendMessage('PluginHandler', PLUGIN_DIED, name)
	
	# -----------------------------------------------------------------------
	
	def SIG_HUP(self, signum, frame):
		self.logger.critical('Received SIGHUP')
		self.__Rehash()
	
	def SIG_TERM(self, signum, frame):
		self.logger.critical('Received SIGTERM')
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
						# Reload our config
						if message.ident == REQ_REHASH:
							self.__Rehash()
						
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
								tolog = "Postman received a message from ghost plugin '%s'" % (child)
								self.logger.warn(tolog)
					
					else:
						# Log the message if debug is enabled
						self.logger.debug(message)
						
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
									tolog = "Invalid target for Message ('%s') : %s" % (name, message)
									self.logger.warn(tolog)
				
				
				# Deliver any waiting messages to children
				for name, child in self.__Children.items():
					if not child.inQueue:
						continue
					
					message = child.inQueue.pop(0)
					
					methname = '_message_%s' % (message.ident)
					if hasattr(child, methname):
						getattr(child, methname)(message)
					else:
						tolog = 'Unhandled message in %s: %s' % (name, message.ident)
						self.logger.debug(tolog)
				
				
				# Poll our sockets
				results = asyncore.poller.poll(0)
				for fd, event in results:
					obj = asyncore.socket_map.get(fd)
					if obj is None:
						tolog = 'Invalid FD for poll(): %d - unregistered' % (fd)
						self.logger.critical(tolog)
						asyncore.poller.unregister(fd)
						continue
					
					if event & select.POLLIN:
						asyncore.read(obj)
					elif event & select.POLLOUT:
						asyncore.write(obj)
					elif event & select.POLLNVAL:
						tolog = "FD %d is still in the poll, but it's closed!" % (fd)
						self.logger.critical(tolog)
					else:
						tolog = 'Bizarre poll response! %d: %d' % (fd, event)
						self.logger.critical(tolog)
				
				
				# Run any always loops
				for meth in self.__run_always:
					meth()
				
				# Do things that don't need to be done all that often
				sometimes_counter = (sometimes_counter + 1) % 5
				if sometimes_counter == 0:
					currtime = time.time()
					
					# See if our log file has to rotate
					#if currtime >= self.__rotate_after:
					#	self.__Log_Rotate()
					
					# If we're shutting down, see if all of our children have
					# stopped.
					if self.__Stopping == 1 and self.__Shutdown_Check():
						return
					
					# Run anything our children want done occasionally
					for meth in self.__run_sometimes:
						meth(currtime)
				
				# Sleep for a while
				time.sleep(0.02)
			
			except KeyboardInterrupt:
				self.__Shutdown('Ctrl-C pressed')
			
			except:
				self.__Log_Exception()
	
	#------------------------------------------------------------------------
	# Our own mangled version of sendMessage
	#------------------------------------------------------------------------
	def sendMessage(self, *args):
		message = Message('Postman', *args)
		
		if message.targets:
			for name in message.targets:
				if name in self.__Children:
					self.__Children[name].inQueue.append(message)
				else:
					tolog = "Invalid target for Message ('%s')" % (name)
					self.logger.warn(tolog)
		
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
		
		tolog = 'Shutting down (%s)...' % (why)
		self.logger.info(tolog)
		
		# Send shutdown messages to everyone
		self.sendMessage(None, REQ_SHUTDOWN, why)
	
	# Don't actually quit until our children have finished shutting down
	def __Shutdown_Check(self):
		alive = [name for name, child in self.__Children.items() if child.stopnow == 0]
		
		# If our children are asleep, and we have no messages, die
		if not alive and not self.inQueue:
			self.logger.info('Shutdown complete')
			return 1
		
		elif alive:
			# If we've been shutting down for a while, just give up
			alives = ', '.join(alive)
			
			if time.time() - self.__Shutdown_Start >= 10:
				tolog = 'Shutdown timeout expired: %s' % (alives)
				self.warn(LOG_ALWAYS, tolog)
				return 1
			
			else:
				tolog = 'Objects still alive: %s' % (alives)
				self.logger.warn(LOG_DEBUG, tolog)
				return 0
		
		return 0
	
	# -----------------------------------------------------------------------
	# Initialise the logging system
	# -----------------------------------------------------------------------
	def __Log_Init(self):
		self.logger = logging.getLogger('hangle')
		self.logger.setLevel(logging.INFO)
		
		# Log to file
		file_handler = logging.handlers.TimedRotatingFileHandler(self.__logfile_filename, 'midnight', 1)
		file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		file_handler.setFormatter(file_formatter)
		self.logger.addHandler(file_handler)
		
		# Log to console
		console_handler = logging.StreamHandler()
		console_handler.setLevel(logging.DEBUG)
		console_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%Y-%m-%d %H:%M:%S')
		console_handler.setFormatter(console_formatter)
		self.logger.addHandler(console_handler)
		
		#self._logger.setLevel(logging.DEBUG)
	
	# -----------------------------------------------------------------------
	# Log an exception nicely
	def __Log_Exception(self, dontcrash=0, exc_info=None):
		if exc_info is not None:
			_type, _value, _tb = exc_info
		else:
			_type, _value, _tb = sys.exc_info()
		
		self.logger.debug('Trapped exception!', exc_info=exc_info)
		
		# If it's a SystemExit exception, we're really meant to die now
		if _type == SystemExit:
			raise
		
		# Extract then delete, to avoid a circular reference thing
		entries = traceback.extract_tb(_tb)
		del _tb
		
		# Find all the filenames involved in the traceback
		crash_files = []
		for entry in entries:
			crash_files.insert(0, entry[:-1][0])
		
		# We crashed during shutdown? Not Good.
		if self.__Stopping == 1:
			self.logger.critical("Exception during shutdown, I'm outta here.")
			sys.exit(1)
		
		# Was it a plugin? If so, we can try shutting it down
		else:
			was_plugin = 0
			for filename in crash_files:
				head, tail = os.path.split(filename)
				if head.endswith('plugins'):
					root, ext = os.path.splitext(tail)
					if root in self.__Children:
						self.sendMessage(root, REQ_SHUTDOWN, None)
						was_plugin = 1
						break
			
			# If it wasn't, and we're supposed to crash, do that
			if not was_plugin and not dontcrash:
				self.__Shutdown('Crashed!')
	
	# -----------------------------------------------------------------------
	# Load config info
	def __Load_Configs(self):
		# Various settings
		self.__logfile_filename = self.Config.get('logging', 'log_file')
		self.__log_debug = self.Config.getboolean('logging', 'debug')
		self.__log_debug_msg = self.Config.getboolean('logging', 'debug_msg')
		self.__log_debug_query = self.Config.getboolean('logging', 'debug_query')
		
		self.__mail_server = self.Config.get('mail', 'server')
		self.__mail_from = self.Config.get('mail', 'from')
		self.__mail_tracebacks = self.Config.get('mail', 'tracebacks').split()
		
		# Don't let foolish people load a plugin twice
		plugins = self.Config.get('plugin', 'plugins').split()
		self.__plugin_list = []
		for name in plugins:
			if name in self.__plugin_list:
				raise Exception, "Plugin '%s' is listed more than once!" % (name)
			self.__plugin_list.append(name)
		
		# Load our plugins
		config_dir = self.Config.get('plugin', 'config_dir')
		if os.path.exists(config_dir):
			for config_file in os.listdir(config_dir):
				if config_file.endswith(".conf"):
					self.Config.read(os.path.join(config_dir, config_file))
		
		# Set up the userlist now
		self.Userlist.Reload()
	
	# Reload our configs and update stuff
	def __Rehash(self):
		self.logger.info('Rehashing...')
		
		# Make a copy of the plugin list
		old_plugin_list = self.__plugin_list[:]
		
		# Delete all of our old sections first
		for section in self.Config.sections():
			junk = self.Config.remove_section(section)
		
		# Re-load the configs
		self.Config.read(self.ConfigFile)
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
						self.logger.info(tolog)
						
						self.sendMessage(plugin_name, REQ_SHUTDOWN, None)
		
		# This is where you'd expect the code to remove any imported plugins
		# that are no longer needed to go, but instead we put it in the handler
		# for the REPLY_SHUTDOWN message we get.
		
		# If no plugins are being reloaded, tell everyone that we have reloaded.
		# Otherwise, we can do that once it's loaded itself :|
		if not self.__reloadme:
			self.sendMessage(None, REQ_REHASH, None)

# ---------------------------------------------------------------------------
