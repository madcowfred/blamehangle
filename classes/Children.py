# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the objects for each 'component' of Blamehangle.
# ---------------------------------------------------------------------------

from classes.Constants import *
from classes.Message import Message

# ---------------------------------------------------------------------------
# This is the main object. The threaded object is a subclass of this.
# ---------------------------------------------------------------------------
class Child:
	def __init__(self, name, outQueue, Config, Userlist):
		# Initialise our variables
		self._name = name
		
		self.outQueue = outQueue
		self.inQueue = []
		self.Config = Config
		self.Userlist = Userlist
		
		self.stoperror = ''
		self.stopnow = 0
		
		# Run our specific setup stuff if we have to
		if hasattr(self, 'setup'):
			self.setup()
	
	# -----------------------------------------------------------------------
	# Get the method that meth_name refers to
	def _Get_Method(self, method_name):
		# We need to fudge things for __ names
		if method_name.startswith('__'):
			method_name = '_%s%s' % (self.__class__.__name__, method_name)
		
		return getattr(self, method_name, None)
	
	# -----------------------------------------------------------------------
	# Default REQ_REHASH handler
	def _message_REQ_REHASH(self, message):
		if hasattr(self, 'rehash'):
			self.rehash()
	
	# -----------------------------------------------------------------------
	# Default REQ_SHUTDOWN handler
	# -----------------------------------------------------------------------
	def _message_REQ_SHUTDOWN(self, message):
		if hasattr(self, 'shutdown'):
			self.shutdown(message)
		
		self.stopnow = 1
		self.sendMessage('Postman', REPLY_SHUTDOWN, None)
	
	# -----------------------------------------------------------------------
	# Send a message, takes the same arguments as Message()
	# -----------------------------------------------------------------------
	def sendMessage(self, *args):
		message = Message(self._name, *args)
		self.outQueue.append(message)
	
	# -----------------------------------------------------------------------
	# Functions for a few messages that we use a lot
	# -----------------------------------------------------------------------
	def privmsg(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_PRIVMSG, [conn, nick, text])
	
	def notice(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_NOTICE, [conn, nick, text])
	
	def putlog(self, level, text):
		self.sendMessage('Postman', REQ_LOG, [level, text])
	
	# Request a DNS lookup
	def dnsLookup(self, trigger, method, host, *args):
		data = [trigger, getattr(method, '__name__', None), host, args]
		self.sendMessage('Resolver', REQ_DNS, data)
	
	# Request a DB query
	def dbQuery(self, trigger, method, query, *args):
		data = [trigger, getattr(method, '__name__', None), query, args]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	# Request a URL fetch
	def urlRequest(self, trigger, method, url, data={}, headers={}):
		req = [trigger, getattr(method, '__name__', None), url, data, headers]
		self.sendMessage('HTTPMonster', REQ_URL, req)

# ---------------------------------------------------------------------------
