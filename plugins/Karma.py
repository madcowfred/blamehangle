#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# Karma plugin
#----------------------------------------------------------------------------
#
# Karma uses the following SQL table:
# CREATE TABLE karma (
#	name char(192) NOT NULL default '',
#	value bigint(20) default NULL,
#	PRIMARY KEY (key)
# ) TYPE=MyISAM;
#

from classes.Plugin import Plugin
from classes.Constants import *
import re

class Karma(Plugin):
	"""
	This is a plugin for Blamehangle that implements user-defined karma.
	
	Karma is represented with an integer value.
	A user on IRC can type either "key++" or "key--" to increment or decrement
	"key"'s karma respectively, or they can type "karma key" to retrieve the
	current karma value for "key".
	Any key without a current karma value is reported as having "neutral"
	karma, meaning zero.
	"""
	
	SELECT_QUERY = "SELECT value FROM karma WHERE name = %s"
	INSERT_QUERY = "INSERT INTO karma VALUES ('%s',%d)"
	UPDATE_QUERY = "UPDATE karma SET value = value + %d WHERE name = %s"
	
	KARMA_PLUS = "KARMA_PLUS"
	KARMA_MINUS = "KARMA_MINUS"
	KARMA_LOOKUP = "KARMA_LOOKUP"
	KARMA_MOD = "KARMA_MOD"

	PLUS_RE = re.compile("^.*(?=\+\+$)")
	MINUS_RE = re.compile("^.*(?=--$)")
	LOOKUP_RE = re.compile("^karma .*(?=$|\?$)")
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(PUBLIC, PLUS_RE, [0], KARMA_PLUS),
		(PUBLIC, MINUS_RE, [0], KARMA_MINUS),
		(PUBLIC, LOOKUP_RE, [0], KARMA_LOOKUP),
		(MSG, LOOKUP_RE, [0], KARMA_LOOKUP)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		[name], event, conn, IRCtype, target, userinfo = message.data
		
		queryObj = whatever(SELECT_QUERY, name, [name, event, conn, IRCtype, target, userinfo])
		self.sendMessage('TheDatabase', DB_QUERY, queryObj)
	
	#------------------------------------------------------------------------

	def _message_WHATEVER_THE_DB_SENDS_BACK(self, message):
		result, [name, event, conn, IRCtype, target, userinfo] = message.data
		
		if event == KARMA_LOOKUP:
			if result == []:
				# no karma!
				replytext = "%s has neutral karma." % name
				reply = [replytext, conn, IRCtype, target, userinfo]
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
			else:
				name, value = result
				replytext = "%s has karma of %d" % (name, value)
				reply = [replytext, conn, IRCtype, target, userinfo]
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
				
		elif event == KARMA_PLUS:
			if result == []:
				# no karma, so insert as 1
				queryObj = whatever(INSERT_QUERY, (1, name), [text, KARMA_MOD, conn, IRCtype, target, userinfo])
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
			else:
				# increment existing karma
				name, value = result
				queryObj = whatever(UPDATE_QUERY, (1, name), [text, KARMA_MOD, conn, IRCtype, target, userinfo])
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
				
		elif event == KARMA_MINUS:
			if result == []:
				# no karma, so insert as -1
				queryObj =  whatever(INSERT_QUERY, (-1, name), [text, KARMA_MOD, conn, IRCtype, target, userinfo])
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
			else:
				# decrement existing karma
				queryObj = whatever(UPDATE_QUERY, (-1, name), [text, KARMA_MOD, conn, IRCtype, target, userinfo])
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)

		elif event == KARMA_MOD:
			# The database just made our requested modifications to the karma
			# table. We don't need to do anything about this, so just pass
			pass

		else:
			# We got a wrong message, what the fuck?
			raise ValueError, "Database sent Karma an erroneous %s" % event

	#------------------------------------------------------------------------
