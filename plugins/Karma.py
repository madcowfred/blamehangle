#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

'Karma. Someone put a useful description here.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

#----------------------------------------------------------------------------

SELECT_QUERY = 'SELECT value FROM karma WHERE name in (%s)'
INSERT_QUERY = 'INSERT INTO karma (name, value) VALUES (%s, %s)'
UPDATE_QUERY = 'UPDATE karma SET value = value + %s WHERE name = %s'

KARMA_PLUS = "KARMA_PLUS"
KARMA_MINUS = "KARMA_MINUS"
KARMA_LOOKUP = "KARMA_LOOKUP"
KARMA_MOD = "KARMA_MOD"

PLUS_RE = re.compile("^(?P<name>.+)\+\+$")
MINUS_RE = re.compile("^(?P<name>.+)--$")
LOOKUP_RE = re.compile("^karma (?P<name>.+)")

KARMA_CHANGE_HELP = '<key>\02++\02 OR <key>\02--\02 : Increment or decrement karma for <key>.'
KARMA_HELP = "\02karma\02 <key> : Look up <key>'s karma level."

KARMA_BEST = 'KARMA_BEST'
BEST_HELP = '\02bestkarma\02 : See the keys with the best karma.'
BEST_QUERY = 'SELECT name, value FROM karma ORDER BY value DESC LIMIT %s'
BEST_RE = re.compile('^bestkarma$')

KARMA_WORST = 'KARMA_WORST'
WORST_HELP = '\02worstkarma\02 : See the keys with the worst karma.'
WORST_QUERY = 'SELECT name, value FROM karma ORDER BY value LIMIT %s'
WORST_RE = re.compile('^worstkarma$')

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
		# Load our options
		self.Options = self.SetupOptions('Karma')
		
		# Set up our combines
		self.__Combines = {}
		for name in self.Config.options('Karma-Combines'):
			self.__Combines[name.lower()] = self.Config.get('Karma-Combines', name).lower().split(',')
	
	def register(self):
		self.setTextEvent(KARMA_PLUS, PLUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_MINUS, MINUS_RE, IRCT_PUBLIC)
		self.setTextEvent(KARMA_LOOKUP, LOOKUP_RE, IRCT_PUBLIC_D, IRCT_MSG)
		
		# bestkarma might be disabled.
		if self.Options['num_best']:
			self.setTextEvent(KARMA_BEST, BEST_RE, IRCT_PUBLIC_D, IRCT_MSG)
			self.setHelp('karma', 'bestkarma', BEST_HELP)
		# worstkarma might be disabled.
		if self.Options['num_worst']:
			self.setTextEvent(KARMA_WORST, WORST_RE, IRCT_PUBLIC_D, IRCT_MSG)
			self.setHelp('karma', 'worstkarma', WORST_HELP)
		
		self.setHelp('karma', 'karma', KARMA_HELP)
		self.setHelp('karma', 'modify', KARMA_CHANGE_HELP)
		
		self.registerEvents()
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
		else:
			self.sendReply(trigger, 'Invalid key name!')
	
	def _trigger_KARMA_PLUS(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			self.dbQuery(trigger, self.__Karma_Plus, SELECT_QUERY, name)
		else:
			self.sendReply(trigger, 'Invalid key name!')
	
	def _trigger_KARMA_MINUS(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			self.dbQuery(trigger, self.__Karma_Minus, SELECT_QUERY, name)
		else:
			self.sendReply(trigger, 'Invalid key name!')
	
	def _trigger_KARMA_BEST(self, trigger):
		self.dbQuery(trigger, self.__Karma_Best, BEST_QUERY, self.Options['num_best'])
	
	def _trigger_KARMA_WORST(self, trigger):
		self.dbQuery(trigger, self.__Karma_Worst, WORST_QUERY, self.Options['num_worst'])
	
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
	
	# Increments a key, or inserts it as 1 if it's not there.
	def __Karma_Plus(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.dbQuery(trigger, self.__Karma_Mod, INSERT_QUERY, name, 1)
		
		else:
			self.dbQuery(trigger, self.__Karma_Mod, UPDATE_QUERY, 1, name)
	
	# Decrements a key, or inserts it as -1 if it's not there.
	def __Karma_Minus(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.dbQuery(trigger, self.__Karma_Mod, INSERT_QUERY, name, -1)
		
		else:
			self.dbQuery(trigger, self.__Karma_Mod, UPDATE_QUERY, -1, name)
	
	# Does nothing except warn if a query failed.
	def __Karma_Mod(self, trigger, result):
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
	
	# Spits out a list of the best karma keys.
	def __Karma_Best(self, trigger, result):
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.sendReply(trigger, 'Nothing has karma yet!')
		
		else:
			bits = []
			for row in result:
				bit = '%s = %s' % (row['name'], row['value'])
				bits.append(bit)
			
			replytext = 'Best \x02%d\x02 karma values: %s' % (self.Options['num_best'], ', '.join(bits))
			self.sendReply(trigger, replytext)
	
	# Spits out a list of the worst karma keys.
	def __Karma_Worst(self, trigger, result):
		if result is None:
			self.sendReply(trigger, 'A database error occurred, eek!')
		
		elif result == ():
			self.sendReply(trigger, 'Nothing has karma yet!')
		
		else:
			bits = []
			for row in result:
				bit = '%s = %s' % (row['name'], row['value'])
				bits.append(bit)
			
			replytext = 'Worst \x02%d\x02 karma values: %s' % (self.Options['num_worst'], ', '.join(bits))
			self.sendReply(trigger, replytext)
	
#----------------------------------------------------------------------------
