# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the objects for each 'component' of Blamehangle.
# ---------------------------------------------------------------------------

from Queue import *

from classes.Common import *
from classes.Constants import *

# ---------------------------------------------------------------------------
# This is the main object. The threaded object is a subclass of this.
# ---------------------------------------------------------------------------
class Child:
	def __init__(self, name, outQueue, Config):
		# Initialise our variables
		self.__name = name
		
		self.outQueue = outQueue
		self.inQueue = Queue(0)
		self.Config = Config
		
		self.stoperror = ''
		self.stopnow = 0
		
		# Rehash (usually read some Config items) if we have to
		#if hasattr(self, 'rehash'):
		#	self.rehash()
		
		# Run our specific setup stuff if we have to
		if hasattr(self, 'setup'):
			self.setup()
	
	# -----------------------------------------------------------------------
	# Check our message queue. If it's not empty, try to find a method to
	# handle the message.
	# -----------------------------------------------------------------------
	def handleMessages(self):
		if self.stopnow:
			return
		
		if not self.inQueue.empty():
			message = self.inQueue.get(0)
			
			try:
				name = '_message_%s' % message.ident
				method = getattr(self, name)
			
			except AttributeError:
				tolog = 'Unhandled message in %s: %s' % (self.__name, message.ident)
				self.putlog(LOG_DEBUG, tolog)
			
			else:
				method(message)
	
	# -----------------------------------------------------------------------
	# Default REQ_REHASH handler
	# -----------------------------------------------------------------------
	def _message_REQ_REHASH(self, message):
		if hasattr(self, 'rehash'):
			tolog = '%s rehashing' % self.__name
			self.putlog(LOG_DEBUG, tolog)

			self.rehash()
			
	
	# -----------------------------------------------------------------------
	# Default REQ_SHUTDOWN handler
	# -----------------------------------------------------------------------
	def _message_REQ_SHUTDOWN(self, message):
		tolog = '%s shutting down' % self.__name
		self.putlog(LOG_ALWAYS, tolog)
		
		if hasattr(self, 'shutdown'):
			self.shutdown(message)
		
		self.stopnow = 1
		self.sendMessage('Postman', REPLY_SHUTDOWN, None)
	
	# -----------------------------------------------------------------------
	# Send a message, takes the same arguments as Message()
	# -----------------------------------------------------------------------
	def sendMessage(self, *args):
		message = Message(self.__name, *args)
		self.outQueue.put(message)
	
	# -----------------------------------------------------------------------
	# Functions for a few messages that we use a lot
	# -----------------------------------------------------------------------
	def privmsg(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_PRIVMSG, [conn, nick, text])
	
	def notice(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_NOTICE, [conn, nick, text])
	
	def putlog(self, level, text):
		self.sendMessage('Postman', REQ_LOG, [level, text])
	
	# Multiple DB queries, be afraid
	def dbQuery(self, returnme, *queries):
		data = [returnme, queries]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	# Timer support?
	def addTimer(self, ident, interval, *args):
		data = [ident, interval, args]
		self.sendMessage('TimeKeeper', REQ_ADD_TIMER, data)
	
	def delTimer(self, ident):
		data = [ident]
		self.sendMessage('TimeKeeper', REQ_DEL_TIMER, data)
