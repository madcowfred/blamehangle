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

import re

from classes.Plugin import Plugin
from classes.Constants import *

class SmartyPants(Plugin):
	"""
	This is the main infobot plugin, the factoid resolver.
	People say stupid shit, and this thing captures it for all time. Then
	they can later ask stupid questions, and we'll find their dumb answers
	for them.

	You can probably also get some random stats about the factoid database,
	too.
	"""

	FACT_SET = "FACT_SET"
	FACT_GET = "FACT_GET"
	FACT_MOD = "FACT_MOD"
	FACT_DEL = "FACT_DEL"
	FACT_INFO = "FACT_INFO"
	FACT_STATUS = "FACT_STATUS"
	FACT_LOCK = "FACT_LOCK"
	
	FACT_UPDATEDB = "FACT_UPDATEDB"

	__GET_QUERY = "SELECT stuff FROM factoids WHERE something = %s"
	__SET_QUERY = "INSERT INTO factoids VALUES (stuff goes here)"

	__GET_RE = re.compile(".*(?=\?$)")
	__SET_RE = re.compile("(?P<key>.+?) (is|are) (?P<value>.+)$")
	__DEL_RE = re.compile("forget (?P<key>.+)$")
	__MOD_RE = re.compile("(?P<key>.+?) =~ (?P<modstring>.+)$")
	__INFO_RE = re.compile("factinfo (?P<key>.+)$")
	__STATUS_RE = re.compile("status$")
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(IRCT_PUBLIC, __GET_RE, [0], FACT_GET),
		(IRCT_MSG, __GET_RE, [0], FACT_GET),
		(IRCT_PUBLIC, __SET_RE, ['key', 'value'], FACT_SET),
		(IRCT_MSG, __SET_RE, ['key', 'value'], FACT_SET),
		(IRCT_PUBLIC, __DEL_RE, ['key'], FACT_DEL),
		(IRCT_MSG, __DEL_RE, ['key'], FACT_DEL),
		(IRCT_PUBLIC, __MOD_RE, ['key', 'modstring'], FACT_MOD),
		(IRCT_MSG, __MOD_RE, ['key', 'modstring'], FACT_MOD),
		(IRCT_PUBLIC, __INFO_RE, ['key'], FACT_INFO),
		(IRCT_MSG, __INFO_RE, ['key'], FACT_INFO),
		(IRCT_PUBLIC, __STATUS_RE, [0], FACT_STATUS),
		(IRCT_MSG, __STATUS_RE, [0], FACT_STATUS)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		key = message.data[0][0]
		
		# First we need to do a SELECT to see if whatever was just requested
		# exists or not
		queryObj = whatever(__GET_QUERY, key, message.data)
		self.sendMessage('TheDatabase', DB_QUERY, queryObj)
	
	#------------------------------------------------------------------------

	def _message_WHATEVER_THE_DB_SENDS_BACK(self, message):
		result, [text, event, conn, IRCtype, target, userinfo] = message.data
		
		if event == FACT_GET:
			self.__fact_get(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_SET:
			self.__fact_set(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_DEL:
			self.__fact_del(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_MOD:
			self.__fact_mod(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_INFO:
			self.__fact_info(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_STATUS:
			self.__fact_status(text, result, conn, IRCtype, target, userinfo)
		elif event == FACT_UPDATE:
			self.__fact_update(text, result, conn, IRCtype, target, userinfo)
		else:
			# Wrong message! Something went wrong
			raise ValueError, "Database sent SmartyPants an erroneous %s" % event
	
	#------------------------------------------------------------------------

	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	def __fact_get(self, text, result, conn, IRCtype, target, userinfo):
		factoid = text[0]

		if result == []:
			# The factoid wasn't in our database
			replytext = self.__random_dunnotext()
		else:
			# We found something!
			# since we only care about the factoid value
			value = result[some index, probably 1]
			prefix = random_foundtext(factoid)
			replytext = "%s %s" % (prefix, value)
		
		reply = [replytext, conn, IRCtype, target, userinfo)
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------

	# A user just tried to set a factoid.. if it doesn't already exist, we
	# will go ahead and add it.
	def __fact_set(self, text, result, conn, IRCtype, target, userinfo):
		key, value = text
		nick = userinfo.nick
		host = userinfo.hostname

		if result == []:
			# Factoid isn't in the DB.. add it!
			queryObj = whatever(__SET_QUERY, (a bunch of stuff), [text, FACT_UPDATE, conn, IRCtype, target, userinfo])
			self.sendMessage('TheDatabase', DB_REQ, queryObj)
		else:
			# The factoid already exists
			replytext = "but '\b%s\b' is already something else..." % key
			reply = [replytext, conn, IRCtype, target, userinfo]
			self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------

	# Someone asked to delete a factoid.
	# XXX: This should be expanded to include user permission stuff, so not just
	# anyone can delete factoids. It's nearly 5am and I'm tired, though.
	def __fact_del(self, text, result, conn, IRCtype, target, userinfo):
		key = text[0]

		if result == []:
			# Factoid wasn't there to delete
			replytext = "I don't have anything called '\b%s\b'" % key
			reply = [replytext, conn, IRCtype, target, userinfo]
			self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
		else:
			queryObj = whatever(__DEL_QUERY, key, [text, FACT_UPDATE, conn, IRCtype, target, userinfo])
			self.sendMessage('TheDatabase', DB_REQ, queryObj)
	
	#------------------------------------------------------------------------

	#------------------------------------------------------------------------

	# The DB has performed our requested update to the factoid table
	def __fact_update(self, text, result, conn, IRCtype, target, userinfo):
		replytext = self.__random_donetext()
		reply = [replytext, conn, IRCtype, target, userinfo]
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------
