#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains (or at least will contain!) the factoid resolver.
#
# XXX: This is not set in stone.
#      Fred, if you come up with something better, editz0r! :)
#
# The factoid resolver uses the following SQL tables:
# CREATE TABLE factoids (
# 	name varchar(64) NOT NULL default '',
#	value text NOT NULL,
#	author_nick varchar(64) default NULL,
#	author_host varchar(192) default NULL,
#	modifier_nick varchar(64) default NULL,
#	modifier_host varchar(192) default NULL,
#	requester_nick varchar(64) default NULL,
#	requester_host varchar(192) default NULL,
#	request_count int(11) NOT NULL default 0,
#	created_time int(11) default NULL,
#	modified_time int(11) default NULL,
#	requested_time int(11) default NULL,
#	PRIMARY KEY (name)
# ) TYPE=MyISAM;
#
# CREATE TABLE factoid_locks (
#	name varchar(64) NOT NULL default '',
#	lock_nick varchar(64) default NULL,
#	lock_host varchar(192) default NULL,
#	lock_time int(11) default NULL,
#	PRIMARY KEY (name)
# ) TYPE=MyISAM;
#

import random
import re
import time
import types

from classes.Plugin import *
from classes.Constants import *

#----------------------------------------------------------------------------

FACT_SET = "FACT_SET"
FACT_GET = "FACT_GET"
FACT_DEL = "FACT_DEL"
FACT_MOD = "FACT_REPLACE"
FACT_INFO = "FACT_INFO"
#FACT_STATUS = "FACT_STATUS"
FACT_LOCK = "FACT_LOCK"

FACT_UPDATEDB = "FACT_MOD"

GET_QUERY = "SELECT name, value FROM factoids WHERE name = %s"
SET_QUERY = "INSERT INTO factoids (name, value, author_nick, author_host, created_time) VALUES (%s, %s, %s, %s, %s)"
INFO_QUERY = "SELECT * FROM factoids WHERE name = %s"

REQUESTED_QUERY = "UPDATE factoids SET request_count = request_count + 1, requester_nick = %s, requester_host = %s WHERE name = %s"

GET_RE = re.compile("^(?P<name>.+?)\??$")
SET_RE = re.compile("^(?P<name>.+?) (is|are) (?P<value>.+)$")
DEL_RE = re.compile("^forget (?P<name>.+)$")
MOD_RE = re.compile("^(?P<name>.+?) =~ (?P<modstring>.+)$")
INFO_RE = re.compile("^factinfo (?P<name>.+)\??$")
#STATUS_RE = re.compile("^status$")

#----------------------------------------------------------------------------

DUNNO = [
	"no idea",
	"I don't know",
	"you got me",
	"not a clue"
]

#----------------------------------------------------------------------------

class SmartyPants(Plugin):
	"""
	This is the main infobot plugin, the factoid resolver.
	People say stupid shit, and this thing captures it for all time. Then
	they can later ask stupid questions, and we'll find their dumb answers
	for them.

	You can probably also get some random stats about the factoid database,
	too.
	"""
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		get_dir = PluginTextEvent(FACT_GET, IRCT_PUBLIC_D, GET_RE)
		get_msg = PluginTextEvent(FACT_GET, IRCT_MSG, GET_RE)
		set_dir = PluginTextEvent(FACT_SET, IRCT_PUBLIC_D, SET_RE)
		set_msg = PluginTextEvent(FACT_SET, IRCT_MSG, SET_RE)
		del_dir = PluginTextEvent(FACT_DEL, IRCT_PUBLIC_D, DEL_RE)
		del_msg = PluginTextEvent(FACT_DEL, IRCT_MSG, DEL_RE)
		#mod_dir =
		#mod_msg =
		info_dir = PluginTextEvent(FACT_INFO, IRCT_PUBLIC_D, INFO_RE)
		info_msg = PluginTextEvent(FACT_INFO, IRCT_MSG, INFO_RE)
		
		# We register GET last, since it's the least specific match we have
		self.register(set_dir, set_msg, del_dir, del_msg, info_dir, info_msg, get_dir, get_msg)
	
	#------------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone wants to lookup a factoid. Make sure they're not really
		# trying to set it first (?)
		if trigger.name == FACT_GET:
			name = trigger.match.group('name')
			if SET_RE.match(name):
				return
			else:
				data = [trigger, (GET_QUERY, [name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		# Someone wants to set a factoid.
		elif trigger.name == FACT_SET:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		elif trigger.name == FACT_INFO:
			name = trigger.match.group('name')
			data = [trigger, (INFO_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	#------------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		trigger, results = message.data
		
		if trigger.name == FACT_GET:
			self.__Fact_Get(trigger, results)
		
		elif trigger.name == FACT_SET:
			self.__Fact_Set(trigger, results)
		
		elif trigger.name == FACT_INFO:
			self.__Fact_Info(trigger, results)
		
		elif trigger.name == FACT_UPDATEDB:
			# The database just made our requested modifications, so we just
			# pass.
			pass
		
		else:
			# We got a wrong message, what the fuck?
			errtext = "Database sent SmartyPants an erroneous %s" % trigger
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	# Return a random dunno string
	# -----------------------------------------------------------------------
	def __Random_Dunno(self):
		a = random.randint(0, len(DUNNO)-1)
		return DUNNO[a]
	
	# -----------------------------------------------------------------------
	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	# -----------------------------------------------------------------------
	def __Fact_Get(self, trigger, results):
		if results == [()]:
			# The factoid wasn't in our database
			replytext = self.__Random_Dunno()
		
		else:
			# We found it!
			row = results[0][0]
			replytext = '%(name)s is %(value)s' % row
			
			# Update the request count and nick
			trigger.name = FACT_UPDATEDB
			
			name = row['name']
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			data = [trigger, (REQUESTED_QUERY, [requester_nick, requester_host, name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# A user just tried to set a factoid.. if it doesn't already exist, we
	# will go ahead and add it.
	# -----------------------------------------------------------------------
	def __Fact_Set(self, trigger, results):
		typ = type(results[0])
		
		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# The factoid wasn't in our database, so insert it
				#INSERT INTO factoids (name, value, author_nick, author_host, created_time)
				trigger.name = FACT_UPDATEDB
				
				name = trigger.match.group('name')
				value = trigger.match.group('value')
				author_nick = trigger.userinfo.nick
				author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
				created_time = time.time()
				data = [trigger, (SET_QUERY, [name, value, author_nick, author_host, created_time])]
				
				self.sendMessage('DataMonkey', REQ_QUERY, data)
			
			else:
				# It was already in our database
				row = results[0][0]
				replytext = "...but '%(name)s' is already something else..." % row
				self.sendReply(trigger, replytext)
		
		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid insertion failed, warning, warning!'
			elif result == 1:
				replytext = 'OK'
			self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	
	# Someone asked to delete a factoid.
	# XXX: This should be expanded to include user permission stuff, so not just
	# anyone can delete factoids. It's nearly 5am and I'm tired, though.
	#def __fact_del(self, text, result, conn, IRCtype, target, userinfo):
	#	key = text[0]
	#	
	#	if result == []:
	#		# Factoid wasn't there to delete
	#		replytext = "I don't have anything called '\b%s\b'" % key
	#		reply = [replytext, conn, IRCtype, target, userinfo]
	#		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	#	else:
	#		queryObj = whatever(__DEL_QUERY, key, [text, FACT_UPDATE, conn, IRCtype, target, userinfo])
	#		self.sendMessage('TheDatabase', DB_REQ, queryObj)
	
	#------------------------------------------------------------------------
	# Someone asked for some info on a factoid.
	#------------------------------------------------------------------------
	def __Fact_Info(self, trigger, results):
		if results == [()]:
			# No such factoid
			replytext = 'there is no such factoid'
		
		else:
			row = results[0][0]
			
			now = time.time()
			
			text = '%(name)s -- created by %(author_nick)s (%(author_host)s), some time ago'
			if row['request_count']:
				#diff = row['requested_time'] - 
				text += '; requested %(request_count)d time(s), last by %(requester_nick)s, some time ago'
			if row['modifier_nick']:
				text += '; last modified by %(modifier_nick)s (%(modifier_host)s), some time ago'
			
			replytext = text % row
		
		self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	
	# The DB has performed our requested update to the factoid table
	#def __fact_update(self, text, result, conn, IRCtype, target, userinfo):
	#	replytext = self.__random_donetext()
	#	reply = [replytext, conn, IRCtype, target, userinfo]
	#	self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------
