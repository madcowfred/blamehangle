#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

'Karma. Someone put a useful description here.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

#----------------------------------------------------------------------------

SELECT_QUERY = "SELECT value FROM karma WHERE name = %s"
INSERT_QUERY = "INSERT INTO karma VALUES (%s,%s)"
UPDATE_QUERY = "UPDATE karma SET value = value + %s WHERE name = %s"

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

PLUS_RE = re.compile("^(?P<name>[ \w]+)\s*\+\+$")
MINUS_RE = re.compile("^(?P<name>[ \w]+)--$")
LOOKUP_RE = re.compile("^karma (?P<name>[ \w]+)")

KARMA_CHANGE_HELP = "<something>\02++\02 OR <something>\02--\02 : Increment or decrement karma for <something>"
KARMA_HELP = "\02karma\02 <something> : Look up <something>'s karma level"

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
	
	def register(self):
		self.setTextEvent(KARMA_PLUS, PLUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_MINUS, MINUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_LOOKUP, LOOKUP_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('karma', 'karma', KARMA_HELP)
		self.setHelp('karma', 'modify', KARMA_CHANGE_HELP)
		self.registerHelp()
	
	#------------------------------------------------------------------------
	
	def _trigger_KARMA_LOOKUP(self, trigger):
		name = trigger.match.group('name').lower().strip()
		if name:
			self.dbQuery(trigger, self.__Karma_Lookup, SELECT_QUERY, name)
	
	def _trigger_KARMA_PLUS(self, trigger):
		name = trigger.match.group('name').lower().strip()
		if name:
			self.dbQuery(trigger, self.__Karma_Plus, SELECT_QUERY, name)
	
	def _trigger_KARMA_MINUS(self, trigger):
		name = trigger.match.group('name').lower().strip()
		if name:
			self.dbQuery(trigger, self.__Karma_Minus, SELECT_QUERY, name)
	
	#------------------------------------------------------------------------
	# Does karma lookups
	def __Karma_Lookup(self, trigger, result):
		name = trigger.match.group('name').lower()
		
		# Error!
		if result is None:
			replytext = 'A database error occurred, eek!'
		
		# No karma for this yet
		elif result == ():
			replytext = '%s has neutral karma' % name
		
		# Some karma for this
		else:
			replytext = '%s has karma of %d' % (name, result[0]['value'])
		
		self.sendReply(trigger, replytext)
	
	# Does ++ stuff
	def __Karma_Plus(self, trigger, result):
		name = trigger.match.group('name').lower()
		
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.dbQuery(trigger, self.__Karma_Mod, INSERT_QUERY, name, 1)
		
		else:
			self.dbQuery(trigger, self.__Karma_Mod, UPDATE_QUERY, 1, name)
	
	# Does -- stuff
	def __Karma_Minus(self, trigger, result):
		name = trigger.match.group('name').lower()
		
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.dbQuery(trigger, self.__Karma_Mod, INSERT_QUERY, name, -1)
		
		else:
			self.dbQuery(trigger, self.__Karma_Mod, UPDATE_QUERY, -1, name)
	
	# Does nothing
	def __Karma_Mod(self, trigger, result):
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
	
#----------------------------------------------------------------------------
