#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# Karma plugin
#----------------------------------------------------------------------------
#
# Karma uses the following SQL table:
# CREATE TABLE karma (
#	name varchar(192) NOT NULL default '',
#	value bigint(20) default NULL,
#	PRIMARY KEY (key)
# ) TYPE=MyISAM;
#

from classes.Plugin import *
from classes.Constants import *
import re

SELECT_QUERY = "SELECT value FROM karma WHERE name = %s"
INSERT_QUERY = "INSERT INTO karma VALUES (%s,%s)"
UPDATE_QUERY = "UPDATE karma SET value = value + %s WHERE name = %s"

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

PLUS_RE = re.compile("(?P<name>^.*)(?=\+\+$)")
MINUS_RE = re.compile("(?P<name>^.*)(?=--$)")
LOOKUP_RE = re.compile("^karma (?P<name>.+)")

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
		inc = PluginTextEvent(KARMA_PLUS, IRCT_PUBLIC, PLUS_RE)
		dec = PluginTextEvent(KARMA_MINUS, IRCT_PUBLIC, MINUS_RE)
		lookup_pub = PluginTextEvent(KARMA_LOOKUP, IRCT_PUBLIC_D, LOOKUP_RE)
		lookup_msg = PluginTextEvent(KARMA_LOOKUP, IRCT_MSG, LOOKUP_RE)

		self.register(inc, dec, lookup_pub, lookup_msg)
	
	#------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		name = trigger.match.group('name')
		name = name.lower()
		data = [trigger, (SELECT_QUERY, [name])]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
		
	#------------------------------------------------------------------------

	def _message_REPLY_QUERY(self, message):
		result, trigger = message.data
		name = trigger.match.group('name')
		
		if trigger.name == KARMA_LOOKUP:
			if result == [()]:
				# no karma!
				replytext = "%s has neutral karma." % name
				self.sendReply(trigger, replytext)
			else:
				info = result[0][0]
				if info['value'] == 0:
					replytext = "%s has neutral karma." % name
				else:
					replytext = "%s has karma of %d" % (name, info['value'])
				self.sendReply(trigger, replytext)
				
		elif trigger.name == KARMA_PLUS:
			trigger.name = KARMA_MOD
			if result == [()]:
				# no karma, so insert as 1
				data = [trigger, (INSERT_QUERY, [name, 1])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
			else:
				# increment existing karma
				data = [trigger, (UPDATE_QUERY, [1, name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
				
		elif trigger.name == KARMA_MINUS:
			trigger.name = KARMA_MOD
			if result == [()]:
				# no karma, so insert as -1
				data = [trigger, (INSERT_QUERY, [name, -1])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
			else:
				# decrement existing karma
				data = [trigger, (UPDATE_QUERY, [-1, name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)

		elif trigger.name == KARMA_MOD:
			# The database just made our requested modifications to the karma
			# table. We don't need to do anything about this, so just pass
			pass

		else:
			# We got a wrong message, what the fuck?
			errtext = "Database sent Karma an erroneous %s" % event
			raise ValueError, errtext

	#------------------------------------------------------------------------
