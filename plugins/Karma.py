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

SELECT_QUERY = "SELECT value FROM karma WHERE name = %s"
INSERT_QUERY = "INSERT INTO karma VALUES ('%s',%d)"
UPDATE_QUERY = "UPDATE karma SET value = value + %d WHERE name = %s"

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

PLUS_RE = re.compile("^.*(?=\+\+$)")
MINUS_RE = re.compile("^.*(?=--$)")
LOOKUP_RE = re.compile("^karma .*(?P<name>?=$|\?$)")

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
	
	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(IRCT_PUBLIC, PLUS_RE, [0], KARMA_PLUS),
		(IRCT_PUBLIC, MINUS_RE, [0], KARMA_MINUS),
		(IRCT_PUBLIC_D, LOOKUP_RE, ['name'], KARMA_LOOKUP),
		(IRCT_MSG, LOOKUP_RE, ['name'], KARMA_LOOKUP)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		[name], event, conn, IRCtype, target, userinfo = message.data

		returnme = [name, event, conn, IRCtype, target, userinfo]
		data = [returnme, (SELECT_QUERY, [])]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	#------------------------------------------------------------------------

	def _message_REPLY_QUERY(self, message):
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
			returnme = [text, KARMA_MOD, conn, IRCtype, target, userinfo]
			if result == []:
				# no karma, so insert as 1
				data = [returnme, (INSERT_QUERY, [1, name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
			else:
				# increment existing karma
				name, value = result
				data = [returnme, (UPDATE_QUERY, [1, name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
				
		elif event == KARMA_MINUS:
			returnme = [text, KARMA_MOD, conn, IRCtype, target, userinfo]
			if result == []:
				# no karma, so insert as -1
				data = [returnme, (INSERT_QUERY, [1, name])]
				self.sendMessage('DataMonkey', DB_QUERY, data)
			else:
				# decrement existing karma
				data = [returnme, (UPDATE_QUERY, [-1, name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)

		elif event == KARMA_MOD:
			# The database just made our requested modifications to the karma
			# table. We don't need to do anything about this, so just pass
			pass

		else:
			# We got a wrong message, what the fuck?
			errtext = "Database sent Karma an erroneous %s" % event
			raise ValueError, errtext

	#------------------------------------------------------------------------
