# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
This file contains the class that all system objects are based on, as well as
Plugin. Don't touch.
"""

import os

from classes.Constants import *
from classes.Message import Message
from classes.OptionsDict import OptionsDict

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
		
		# If this child wants to use some database tables, we might have to
		# create them now
		if hasattr(self, '_UsesDatabase'):
			filename = '%s.sql' % (self._UsesDatabase)
			schema = os.path.join('schemas', filename)
			if not os.path.exists(schema):
				tolog = "%s defines _UsesDatabase, but '%s' doesn't exist!" % (self._name, schema)
				self.putlog(LOG_WARNING, tolog)
				return
			# Load up the schema, look for the first table name
			try:
				f = open(schema, 'r')
				for line in f:
					if line.lower().startswith('create table '):
						query = 'SELECT * FROM %s LIMIT 1' % line.split()[2]
						self.dbQuery(schema, self._DB_Check, query)
						f.close()
						return
				f.close()
			except Exception, msg:
				tolog = "Error while trying to check DB for %s: %s" % (self._name, msg)
				self.putlog(LOG_WARNING, tolog)
			else:
				tolog = "%s defines _UsesDatabase, but '%s' contains no CREATE TABLE statements!" % (self._name, schema)
				self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# If the database table doesn't exist, we get to create it now
	def _DB_Check(self, schema, result):
		if result is None:
			tolog = "Creating database table for %s!" % (self._name)
			self.putlog(LOG_WARNING, tolog)
			
			query = open(schema, 'r').read().replace('\n', '').replace('\r', '')
			self.dbQuery(schema, self._DB_Create, query)
	
	# If the create failed, cry a bit
	def _DB_Create(self, schema, result):
		if result is None:
			tolog = "Creating table for %s failed!" % (self._name)
		else:
			tolog = "Created table for %s." % (self._name)
		
		self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Get the method that meth_name refers to
	def _Get_Method(self, method_name):
		# We need to fudge things for __ names
		if method_name.startswith('__'):
			method_name = '_%s%s' % (self._name, method_name)
		
		return getattr(self, method_name, None)
	
	# -----------------------------------------------------------------------
	# Default REQ_REHASH handler
	def _message_REQ_REHASH(self, message):
		if hasattr(self, 'rehash'):
			self.rehash()
	
	# -----------------------------------------------------------------------
	# Default REQ_SHUTDOWN handler
	def _message_REQ_SHUTDOWN(self, message):
		if hasattr(self, 'shutdown'):
			self.shutdown(message)
		
		self.stopnow = 1
		self.sendMessage('Postman', REPLY_SHUTDOWN, None)
	
	# Default DNS reply handler, eek
	def _message_REPLY_DNS(self, message):
		trigger, methname, hosts, args = message.data
		if methname is None:
			return
		
		method = self._Get_Method(methname)
		if method is not None:
			try:
				method(trigger, hosts, args)
			except:
				if hasattr(self, 'sendReply'):
					replytext = '%s crashed in %s()!' % (self._name, methname)
					self.sendReply(trigger, replytext)
				raise
		else:
			raise NameError, 'define %s.%s or override _message_REPLY_DNS' % (self._name, methname)
	
	# Default query reply handler, eek
	def _message_REPLY_QUERY(self, message):
		trigger, methname, result = message.data
		if methname is None:
			return
		
		method = self._Get_Method(methname)
		if method is not None:
			try:
				method(trigger, result)
			except:
				if hasattr(self, 'sendReply'):
					replytext = '%s crashed in %s()!' % (self._name, methname)
					self.sendReply(trigger, replytext)
				raise
		else:
			raise NameError, 'define %s.%s or override _message_REPLY_QUERY' % (self._name, methname)
	
	# Default URL reply handler, eek
	def _message_REPLY_URL(self, message):
		trigger, methname, resp = message.data
		
		# Failed
		if resp.data is None:
			if hasattr(self, 'sendReply'):
				if not hasattr(self, '_QuietURLErrors'):
					if not hasattr(self, '_VerboseURLErrors'):
						self.sendReply(trigger, 'HTTP transfer failed, ruh-roh.')
					else:
						replytext = 'HTTP transfer from %s failed, ruh-roh.' % resp.url
						self.sendReply(trigger, replytext)
			return
		
		# OK!
		if methname is None:
			return
		
		method = self._Get_Method(methname)
		if method is not None:
			try:
				method(trigger, resp)
			except:
				if hasattr(self, 'sendReply'):
					replytext = '%s crashed in %s()!' % (self._name, methname)
					self.sendReply(trigger, replytext)
				raise
		else:
			raise NameError, 'define %s.%s or override _message_REPLY_URL' % (self._name, methname)
	
	# -----------------------------------------------------------------------
	# Send a message, takes the same arguments as Message()
	def sendMessage(self, *args):
		message = Message(self._name, *args)
		self.outQueue.append(message)
	
	# -----------------------------------------------------------------------
	# Shortcut methods for a few messages that we use a lot
	def privmsg(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_PRIVMSG, [conn, nick, text])
	
	def notice(self, conn, nick, text):
		self.sendMessage('ChatterGizmo', REQ_NOTICE, [conn, nick, text])
	
	def putlog(self, level, text):
		self.sendMessage('Postman', REQ_LOG, [level, text])
	
	# Request a DB query
	def dbQuery(self, trigger, method, query, *args):
		data = [trigger, getattr(method, '__name__', None), query, args]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	# Request a DNS lookup
	def dnsLookup(self, trigger, method, host, *args):
		data = [trigger, getattr(method, '__name__', None), host, args]
		self.sendMessage('Resolver', REQ_DNS, data)
	
	# Request a URL fetch
	def urlRequest(self, trigger, method, url, data={}, headers={}):
		req = [trigger, getattr(method, '__name__', None), url, data, headers]
		self.sendMessage('HTTPMonster', REQ_URL, req)
	
	# -----------------------------------------------------------------------
	# Load all options in section into a dictionary. This does some automatic
	# conversions: number strings become longs, per network/channel configs
	# become dictionaries.
	def OptionsDict(self, section, autosplit=False):
		dict = OptionsDict()
		
		for option in self.Config.options(section):
			value = self.Config.get(section, option)
			if value.isdigit():
				value = long(value)
			
			parts = option.split('.')
			# If it has no periods, it's just an option
			if len(parts) == 1:
				dict[option] = value
			# If it has one period, it's a per-network config
			elif len(parts) == 2:
				if autosplit is True:
					dict.setdefault(parts[0], {})[parts[1]] = value.split()
				else:
					dict.setdefault(parts[0], {})[parts[1]] = value
			# If it has two periods, it's a per-channel config
			elif len(parts) == 3:
				if autosplit:
					dict.setdefault(parts[0], {}).setdefault(parts[1], {})[parts[2]] = value.split()
				else:
					dict.setdefault(parts[0], {}).setdefault(parts[1], {})[parts[2]] = value
			# What the hell is it?
			else:
				tolog = "Unknown option '%s'" % (option)
				self.putlog(LOG_WARNING, tolog)
		
		return dict
	
	# Load all options in a section into a list. This only keeps the values,
	# option names are discarded.
	def OptionsList(self, section):
		values = []
		for option in self.Config.options(section):
			values.append(self.Config.get(section, option))
		return values

# ---------------------------------------------------------------------------
