# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
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
This file contains the class that all system objects are based on, as well as
Plugin. Don't touch.
"""

import cPickle
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
				data = open(schema, 'r').read().replace('\n', '').replace('\r', '')
				queries = data.split(';')
				
				while 1:
					query = queries[0]
					if query.lower().startswith('create table '):
						testquery = 'SELECT * FROM %s LIMIT 1' % (query.split(None, 4)[2])
						self.dbQuery(queries, self._DB_Check, testquery)
						return
					else:
						try:
							queries.remove(0)
						except ValueError:
							break
			
			except Exception, msg:
				tolog = "Error while trying to check DB for %s: %s" % (self._name, msg)
				self.putlog(LOG_WARNING, tolog)
			
			else:
				tolog = "%s defines _UsesDatabase, but '%s' contains no CREATE TABLE statements!" % (self._name, schema)
				self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# If the database table doesn't exist, we get to create it now
	def _DB_Check(self, queries, result):
		query = queries.pop(0)
		
		if result is None:
			tolog = "Creating database table for %s!" % (self._name)
			self.putlog(LOG_WARNING, tolog)
			
			self.dbQuery(query, self._DB_Create, query)
		
		if queries:
			while 1:
				query = queries[0]
				if query.lower().startswith('create table '):
					testquery = 'SELECT * FROM %s LIMIT 1' % (query.split(None, 4)[2])
					self.dbQuery(queries, self._DB_Check, testquery)
					return
				else:
					try:
						queries.remove(0)
					except ValueError:
						break
	
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
					replytext = 'unhandled exception in %s.%s()!' % (self._name, methname)
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
					replytext = 'unhandled exception in %s.%s()!' % (self._name, methname)
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
					replytext = 'unhandled exception in %s.%s()!' % (self._name, methname)
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
	
	# -----------------------------------------------------------------------
	# Save an object to disk as a pickle
	def savePickle(self, filename, obj):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, 'wb')
		except:
			tolog = "Unable to open %s for writing" % (filename)
			self.putlog(LOG_WARNING, tolog)
			return
		
		try:
			cPickle.dump(obj, f, 1)
		except Exception, msg:
			tolog = "Saving pickle to '%s' failed: %s" % (filename, msg)
			self.putlog(LOG_WARNING, tolog)
		else:
			tolog = "Saved pickle to '%s'" % (filename)
			self.putlog(LOG_DEBUG, tolog)
		
		f.close()
	
	def loadPickle(self, filename):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, 'rb')
		except:
			return None
		
		try:
			obj = cPickle.load(f)
		except Exception, msg:
			tolog = "Loading pickle from '%s' failed: %s" % (filename, msg)
			self.putlog(LOG_WARNING, tolog)
			return None
		else:
			tolog = "Loaded pickle from '%s'" % (filename)
			self.putlog(LOG_DEBUG, tolog)
			return obj

# ---------------------------------------------------------------------------
