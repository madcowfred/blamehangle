#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

'Karma. Someone put a useful description here.'

import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin
from classes.SimpleCacheDict import SimpleCacheDict

#----------------------------------------------------------------------------

SELECT_QUERY = 'SELECT value FROM karma WHERE name in (%s)'
INSERT_QUERY = 'INSERT INTO karma (name, value) VALUES (%s, %s)'
UPDATE_QUERY = 'UPDATE karma SET value = value + %s WHERE name = %s'
BEST_QUERY = 'SELECT name, value FROM karma ORDER BY value DESC LIMIT %s'
WORST_QUERY = 'SELECT name, value FROM karma ORDER BY value LIMIT %s'

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
	
	_HelpSection = 'karma'
	_UsesDatabase = 'Karma'
	
	def setup(self):
		self.__Build_Translation()
		
		self.HostCache = SimpleCacheDict(1)
		self.NameCache = SimpleCacheDict(1)
		self.LastRequests = []
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('Karma')
		
		# Update our cache lengths and expire them
		self.HostCache.cachesecs = self.Options['host_request_delay']
		self.HostCache.expire()
		self.NameCache.cachesecs = self.Options['key_request_delay']
		self.NameCache.expire()
		
		# Set up our combines
		self.__Combines = {}
		for name in self.Config.options('Karma-Combines'):
			self.__Combines[name.lower()] = self.Config.get('Karma-Combines', name).lower().split(',')
	
	def register(self):
		self.addTextEvent(
			method = self.__Query_Lookup,
			regexp = r'^karma (?P<name>.+)',
			help = ('karma', "\02karma\02 <key> : Look up <key>'s karma level."),
		)
		# Only plus gets the help for changes
		self.addTextEvent(
			method = self.__Query_Plus,
			regexp = r'^(?P<name>.+)\+\+$',
			IRCTypes = (IRCT_PUBLIC,),
			help = ('modify', '<key>\02++\02 OR <key>\02--\02 : Increment or decrement karma for <key>.'),
		)
		self.addTextEvent(
			method = self.__Query_Minus,
			regexp = r'^(?P<name>.+)\-\-$',
			IRCTypes = (IRCT_PUBLIC,),
		)
		
		# bestkarma might be disabled.
		if self.Options['num_best']:
			self.addTextEvent(
				method = self.__Query_Best,
				regexp = r'^bestkarma$',
				help = ('bestkarma', '\02bestkarma\02 : See the keys with the best karma.'),
			)
		# worstkarma might be disabled.
		if self.Options['num_worst']:
			self.addTextEvent(
				method = self.__Query_Worst,
				regexp = r'^worstkarma$',
				help = ('worstkarma', '\02worstkarma\02 : See the keys with the worst karma.'),
			)
	
	#------------------------------------------------------------------------
	
	def __Build_Translation(self):
		#    space   #   '   +   -   .   [   ]   ^   _   |
		chars = [32, 35, 39, 43, 45, 46, 91, 93, 94, 95, 124]
		# 0-9 (48-57)
		chars += range(48, 58)
		# a-z (97-122)
		chars += range(97, 123)
		
		# Build the table! \x00 is our 'bad' char
		trans = ['\x00'] * 256
		for i in chars:
			trans[i] = chr(i)
		self.__trans = ''.join(trans)
	
	# Return a sanitised karma key name.
	def __Sane_Name(self, trigger):
		newname = trigger.match.group('name')
		
		# lower case
		newname = newname.lower()
		# translate the name according to our table
		newname = newname.translate(self.__trans).replace('\x00', '')
		# strip leading and trailing spaces
		newname = newname.strip()
		
		return newname
	
	# Check our various caches to make sure people aren't spamming us.
	def __Check_Spam(self, host, name):
		# User host
		if host in self.HostCache:
			self.HostCache[host] = 1
			return True
		self.HostCache[host] = 1
		
		# Key name
		if name in self.NameCache:
			self.NameCache[name] = 1
			return True
		self.NameCache[name] = 1
		
		# Recent requests
		now = time.time()
		self.LastRequests = [t for t in self.LastRequests if now - t < self.Options['total_request_delay']]
		if len(self.LastRequests) >= self.Options['total_request_count']:
			return True
		self.LastRequests.append(now)
		
		return False
	
	#------------------------------------------------------------------------
	
	def __Query_Lookup(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			# See if this key needs some combining
			combo = 0
			if name in self.__Combines:
				combo = 1
			else:
				for k, v in self.__Combines.items():
					if name in v:
						combo = 1
						name = k
						break
			
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
	
	def __Query_Plus(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			if self.__Check_Spam(trigger.userinfo.host, name):
				return
			
			self.dbQuery(trigger, self.__Karma_Plus, SELECT_QUERY, name)
		else:
			self.sendReply(trigger, 'Invalid key name!')
	
	def __Query_Minus(self, trigger):
		name = self.__Sane_Name(trigger)
		if name:
			if self.__Check_Spam(trigger.userinfo.host, name):
				return
			
			self.dbQuery(trigger, self.__Karma_Minus, SELECT_QUERY, name)
		else:
			self.sendReply(trigger, 'Invalid key name!')
	
	def __Query_Best(self, trigger):
		self.dbQuery(trigger, self.__Karma_Best, BEST_QUERY, self.Options['num_best'])
	
	def __Query_Worst(self, trigger):
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
			total = sum([row['value'] for row in result])
			if hasattr(trigger, 'karmaname'):
				replytext = '%s has karma of %d' % (trigger.karmaname, total)
			else:
				replytext = '%s has karma of %d' % (name, total)
		
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

# ---------------------------------------------------------------------------
