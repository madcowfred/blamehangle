#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

'Karma. Someone put a useful description here.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

#----------------------------------------------------------------------------

SELECT_QUERY = "SELECT value FROM karma WHERE name in (%s)"
INSERT_QUERY = "INSERT INTO karma VALUES (%s,%s)"
UPDATE_QUERY = "UPDATE karma SET value = value + %s WHERE name = %s"

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

#PLUS_RE = re.compile("^(?P<name>[ \w]+)\s*\+\+$")
#MINUS_RE = re.compile("^(?P<name>[ \w]+)--$")
PLUS_RE = re.compile("^(?P<name>.+)\+\+$")
MINUS_RE = re.compile("^(?P<name>.+)--$")
LOOKUP_RE = re.compile("^karma (?P<name>.+)")

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
	
	def setup(self):
		# build our translation string
		self.__Build_Translation()
		
		self.rehash()
	
	def rehash(self):
		# Load our karma combines
		self.__Combines = {}
		
		for name in self.Config.options('Karma-Combines'):
			self.__Combines[name.lower()] = self.Config.get('Karma-Combines', name).lower().split('|')
	
	def register(self):
		self.setTextEvent(KARMA_PLUS, PLUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_MINUS, MINUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_LOOKUP, LOOKUP_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('karma', 'karma', KARMA_HELP)
		self.setHelp('karma', 'modify', KARMA_CHANGE_HELP)
		self.registerHelp()
	
	#------------------------------------------------------------------------
	
	def __Build_Translation(self):
		#    space   #   '   +   -   .   [   ]   ^   _   |
		chars = [32, 35, 39, 43, 45, 46, 91, 93, 94, 95, 124]
		# 0-9 (48-57)
		chars += range(48, 58)
		# A-Z (65-90)
		chars += range(65, 91)
		# a-z (97-122)
		chars += range(97, 123)
		
		# Build the table! \x00 is our 'bad' char
		self.__trans = ''
		for i in range(256):
			if i in chars:
				self.__trans += chr(i)
			else:
				self.__trans += '\x00'
	
	# Return a sanitised karma key name.
	def __Sane_Name(self, trigger):
		newname = trigger.match.group('name')
		
		# lower case
		newname = newname.lower()
		# translate the name according to our table
		newname = newname.translate(self.__trans)
		# remove any bad chars now
		newname = newname.replace('\x00', '')
		# strip leading and trailing spaces
		newname = newname.strip()
		
		return newname
	
	#------------------------------------------------------------------------
	
	def _trigger_KARMA_LOOKUP(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			# See if this key needs some combining
			combo = 0
			if name in self.__Combines:
				combo = 1
			else:
				ks = [k for k, v in self.__Combines.items() if name in v]
				if ks:
					combo = 1
					name = ks[0]
			
			# Looks like it does
			if combo:
				args = [name]
				args.extend(self.__Combines[name])
				querybit = ', '.join(['%s'] * len(args))
				query = SELECT_QUERY % querybit
				
				trigger.karmaname = name
				
				self.dbQuery(trigger, self.__Karma_Lookup, query, *args)
			
			else:
				self.dbQuery(trigger, self.__Karma_Lookup, SELECT_QUERY, name)
	
	def _trigger_KARMA_PLUS(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			self.dbQuery(trigger, self.__Karma_Plus, SELECT_QUERY, name)
	
	def _trigger_KARMA_MINUS(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			self.dbQuery(trigger, self.__Karma_Minus, SELECT_QUERY, name)
	
	#------------------------------------------------------------------------
	# Does karma lookups
	def __Karma_Lookup(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			replytext = 'A database error occurred, eek!'
		
		# No karma for this yet
		elif result == ():
			replytext = '%s has neutral karma' % name
		
		# Some karma for this
		else:
			# Combined result
			if len(result) > 1:
				total = sum([row['value'] for row in result])
				replytext = '%s has karma of %d' % (trigger.karmaname, total)
			else:
				replytext = '%s has karma of %d' % (name, result[0]['value'])
		
		self.sendReply(trigger, replytext)
	
	# Does ++ stuff
	def __Karma_Plus(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.dbQuery(trigger, self.__Karma_Mod, INSERT_QUERY, name, 1)
		
		else:
			self.dbQuery(trigger, self.__Karma_Mod, UPDATE_QUERY, 1, name)
	
	# Does -- stuff
	def __Karma_Minus(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
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
