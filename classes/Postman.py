# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the Postman class, which handles inter-object messages
# and logging. Try not to touch this :)
# ---------------------------------------------------------------------------

import exceptions, sys, time, traceback
from Queue import *

# ---------------------------------------------------------------------------

from classes.Common import *
from Constants import *

from Plugins import *
from ChatterGizmo import ChatterGizmo

#from OfferBot import Chatterbox
#from FileMonster import FileMonster
#from PackMan import PackMan
#from Queuer import Queuer
#from Admin import HeadHoncho

# ---------------------------------------------------------------------------

class Postman:
	def __init__(self, ConfigFile, Config):
		self.ConfigFile = ConfigFile
		self.Config = Config
		
		self.__Stopping = 0
		
		self.__logfile_filename = self.Config.get('files', 'log_file')
		
		
		# Open our log file and rotate it if we have to
		self.__Log_Open()
		self.__Log_Rotate()
		
		
		# Initialise the global message queue
		self.inQueue = Queue(0)
		
		
		# Create our children
		self.__Children = {}

		#system = [ ChatterGizmo, PluginHandler, WhateverTheDatabaseIs ]
		system = [ ChatterGizmo ]
		
		for cls in system:
			instance = cls(cls.__name__, self.inQueue, self.Config)
			self.__Children[cls.__name__] = instance
		
		#plugins = self.__Children['PluginHandler'].pluginList()
		#
		#for cls in plugins:
		#	instance = cls(cls.__name__, self.inQueue, self.Config)
		#	self.__Children[cls.__name__] = instance
	
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
				if not self.inQueue.empty():
					message = self.inQueue.get(0)
					
					# If it's targeted at us, process it
					if len(message.targets) == 1 and message.targets[0] == 'Postman':
						if message.ident == REQ_LOG:
							self.__Log(*message.data)
						
						# Reload our config
						elif message.ident == REQ_LOAD_CONFIG:
							self.__Log(LOG_ALWAYS, 'Rehashing config...')
							
							self.Config.read(self.ConfigFile)
							
							self.sendMessage(None, REQ_REHASH, None)
							self.sendMessage('HeadHoncho', REPLY_LOAD_CONFIG, message.data)
							
							#mess = Message('Postman', None, REQ_REHASH, [])
							#for child in self.__Children.values():
							#	child.inQueue.put(mess)
						
						elif message.ident == REQ_SHUTDOWN:
							self.__Shutdown(message.data[0])
					
					else:
						# Log the message if debug is enabled
						self.__Log(LOG_DEBUG, message)
						
						# If it's a global message, send it to everyone
						if len(message.targets) == 0:
							for child in self.__Children.values():
								child.inQueue.put(message)
						
						# If it's not, send it to each thread listed in targets
						else:
							for name in message.targets:
								try:
									self.__Children[name].inQueue.put(message)
								
								except KeyError:
									tolog = "WARNING: invalid target for Message ('%s')" % name
									self.__Log(LOG_ALWAYS, tolog)
									
									pass
				
				
				# Check for messages, then run the main loops
				for child in self.__Children.values():
					child.handleMessages()
					
					child.run_always()
				
				
				# Do things that don't need to be done all that often
				sometimes_counter += 1
				if sometimes_counter == 10:
					sometimes_counter = 0
					
					currtime = _time()
					
					# See if our log file has to rotate
					self.__Log_Rotate()
					
					# If we're shutting down, see if all of our children have
					# stopped.
					if self.__Stopping == 1:
						self.__Shutdown_Check()
					
					# Run anything our children want done occasionally
					for child in self.__Children.values():
						child.run_sometimes(currtime)
				
				
				# Sleep for a while
				_sleep(0.02)
		
			except KeyboardInterrupt:
				self.__Shutdown('Ctrl-C pressed')
				pass
			
			except:
				trace = sys.exc_info()
				
				# If it's a SystemExit, we're really meant to be stopping now
				if trace[0] == exceptions.SystemExit:
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
				
				
				self.__Shutdown('Crashed!')
	
	#------------------------------------------------------------------------
	# Our own mangled version of sendMessage
	#------------------------------------------------------------------------
	def sendMessage(self, *args):
		message = Message('Postman', *args)
		
		# Log the message if debug is enabled
		self.__Log(LOG_DEBUG, message)
		
		if message.targets:
			for name in message.targets:
				try:
					self.__Children[name].inQueue.put(message)
				
				except KeyError:
					tolog = "WARNING: invalid target for Message ('%s')" % name
					self.__Log(LOG_ALWAYS, tolog)
		
		else:
			for child in self.__Children.values():
				child.inQueue.put(message)
	
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
		
		# Send shutdown messages to Queuer, FileMonster and HeadHoncho.
		# PackMan and Chatterbox need to do some things after FileMonster
		# has finished.
		self.sendMessage(['Queuer', 'FileMonster', 'HeadHoncho'], REQ_SHUTDOWN, [why])
	
	# Don't actually quit until our children have finished shutting down
	def __Shutdown_Check(self):
		alive = [name for name, child in self.__Children.items() if child.stopnow == 0]
		
		# If our children are asleep, and we have no messages, die
		if not alive and self.inQueue.empty():
			self.__Log(LOG_ALWAYS, 'Shutdown complete')
			
			sys.exit(1)
	
	# -----------------------------------------------------------------------
	
	def __Log_Open(self):
		try:
			self.__logfile = open(self.__logfile_filename, 'a+')
		
		except:
			print "Failed to open our log file!"
			sys.exit(-1)
		
		else:
			self.__logfile.seek(0, 0)
			
			firstline = self.__logfile.readline()
			if firstline:
				self.__logdate = firstline[0:10]
				self.__logfile.seek(0, 2)
			
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
		
		if level == LOG_ALWAYS:
			print timeshort, text
			
			tolog = "%s %s\n" % (timelong, text)
		
		elif level == LOG_WARNING:
			print timeshort, 'WARNING:', text
			
			tolog = '%s WARNING: %s\n' % (timelong, text)
		
		elif level == LOG_DEBUG:
			if self.Config.getint('other', 'debug'):
				print timeshort, '[DEBUG]', text
				
				tolog = "%s [DEBUG] %s\n" % (timelong, text)
			
			else:
				return
		
		self.__logfile.write(tolog)
		self.__logfile.flush()

# ---------------------------------------------------------------------------
