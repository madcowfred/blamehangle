#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# Karma plugin

import re

from classes.Plugin import *
from classes.Constants import *

#----------------------------------------------------------------------------

SELECT_QUERY = "SELECT value FROM karma WHERE name = %s"
INSERT_QUERY = "INSERT INTO karma VALUES (%s,%s)"
UPDATE_QUERY = "UPDATE karma SET value = value + %s WHERE name = %s"

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

PLUS_RE = re.compile("(?P<name>^.+)(?=\+\+$)")
MINUS_RE = re.compile("(?P<name>^.+)(?=--$)")
LOOKUP_RE = re.compile("^karma (?P<name>.+)")

KARMA_CHANGE_HELP = "'<something>\02++\02' OR '<something>\02--\02' : Increment or decrement karma for <something>"
KARMA_HELP = "'\02karma\02 <something>' : Look up <something>'s karma level"

#----------------------------------------------------------------------------

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
		
		self.setHelp('karma', 'karma', KARMA_HELP)
		self.setHelp('karma', 'modify', KARMA_CHANGE_HELP)
		
		self.registerHelp()
	
	#------------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		name = trigger.match.group('name')
		name = name.lower()
		query = (SELECT_QUERY, name)
		self.dbQuery(trigger, query)
	
	#------------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		trigger, result = message.data
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
				query = (INSERT_QUERY, name, 1)
				self.dbQuery(trigger, query)
			else:
				# increment existing karma
				query = (UPDATE_QUERY, 1, name)
				self.dbQuery(trigger, query)
		
		elif trigger.name == KARMA_MINUS:
			trigger.name = KARMA_MOD
			if result == [()]:
				# no karma, so insert as -1
				query = (INSERT_QUERY, name, -1)
				self.dbQuery(trigger, query)
			else:
				# decrement existing karma
				query = (UPDATE_QUERY, -1, name)
				self.dbQuery(trigger, query)
		
		elif trigger.name == KARMA_MOD:
			# The database just made our requested modifications to the karma
			# table. We don't need to do anything about this, so just pass
			pass
		
		else:
			# We got a wrong message, what the fuck?
			errtext = "Database sent Karma an erroneous %s" % event
			raise ValueError, errtext
	
#----------------------------------------------------------------------------
