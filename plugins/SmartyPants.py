# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
An implementation of an infobot, similar to... every other infobot. This is
the scariest plugin included with the bot, due to the mildly complicated
database trickery.
"""

import random
import re
import time
import types

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

GET_QUERY = "SELECT name, value, locker_nick FROM factoids WHERE name = %s"

SUB_CHAN_RE = re.compile(r'(?<!\\)\$channel\b')
SUB_DATE_RE = re.compile(r'(?<!\\)\$date\b')
SUB_NICK_RE = re.compile(r'(?<!\\)\$nick\b')

SET_QUERY = "INSERT INTO factoids (name, value, author_nick, author_host, created_time) VALUES (%s, %s, %s, %s, %s)"

# Build the giant 'no, ' query
NO_QUERY  = "UPDATE factoids SET value = %s, author_nick = %s, author_host = %s, created_time = %s"
NO_QUERY += ", modifier_nick = '', modifier_host = '', modified_time = NULL, requester_nick = ''"
NO_QUERY += ", requester_host = '', requested_time = NULL, request_count = 0, locker_nick = ''"
NO_QUERY += ", locker_host = '', locked_time = NULL WHERE name = %s"

FORGET_QUERY = "DELETE FROM factoids WHERE name = %s"

LOCK_QUERY = "UPDATE factoids SET locker_nick = %s, locker_host = %s, locked_time = %s WHERE name = %s"
UNLOCK_QUERY = "UPDATE factoids SET locker_nick = NULL, locker_host = NULL, locked_time = NULL WHERE name = %s"

INFO_QUERY = "SELECT * FROM factoids WHERE name = %s"

STATUS_QUERY = "SELECT count(*) AS total FROM factoids"

LISTKEYS_QUERY = "SELECT name FROM factoids WHERE name LIKE '%%%s%%'"
LISTVALUES_QUERY = "SELECT name FROM factoids WHERE value LIKE '%%%s%%'"

# misc db queries
MOD_QUERY = "UPDATE factoids SET value = %s, modifier_nick = %s, modifier_host = %s, modified_time = %s WHERE name = %s"
REQUESTED_QUERY = "UPDATE factoids SET request_count = request_count + 1, requester_nick = %s, requester_host = %s, requested_time = %s WHERE name = %s"

# match <reply> or <action> factoids
REPLY_ACTION_RE = re.compile(r'^<(?P<type>reply|action)>\s*(?P<value>.+)$', re.I)
# match <null> factoids
NULL_RE = re.compile(r'^<null>\s*$', re.I)
# match redirected factoids
REDIRECT_RE = re.compile(r'^see(: *| +)(?P<factoid>.{1,64})$')

# ---------------------------------------------------------------------------
# Range for factoid name
MIN_FACT_NAME_LENGTH = 16
DEF_FACT_NAME_LENGTH = 32
MAX_FACT_NAME_LENGTH = 64
# Range for factoid value
MIN_FACT_VALUE_LENGTH = 200
DEF_FACT_VALUE_LENGTH = 800
MAX_FACT_VALUE_LENGTH = 2000

MAX_FACT_SEARCH_RESULTS = 40

# ---------------------------------------------------------------------------

OK = (
	"OK",
	"you got it",
	"done",
	"okay",
	"okie",
	"as you wish",
	"by your command",
	"yes sir",
)

DUNNO = (
	"no idea",
	"I don't know",
	"you got me",
	"not a clue",
	"nfi",
	"I dunno",
	"I'm not an encyclopedia",
)

# ---------------------------------------------------------------------------

class SmartyPants(Plugin):
	"""
	This is the main infobot plugin, the factoid resolver.
	People say stupid shit, and this thing captures it for all time. Then
	they can later ask stupid questions, and we'll find their dumb answers
	for them.

	You can probably also get some random stats about the factoid database,
	too.
	"""
	
	_HelpSection = 'infobot'
	_UsesDatabase = 'SmartyPants'
	
	def setup(self):
		self.__start_time = time.asctime()
		self.__requests = 0
		self.__dunnos = 0
		self.__sets = 0
		self.__modifys = 0
		self.__dels = 0
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('Infobot', autosplit=True)
		
		self.Options['max_fact_name_length'] = max(MIN_FACT_NAME_LENGTH, min(MAX_FACT_NAME_LENGTH,
			self.Options.get('max_fact_name_length', DEF_FACT_NAME_LENGTH)))
		self.Options['max_fact_value_length'] = max(MIN_FACT_VALUE_LENGTH, min(MAX_FACT_VALUE_LENGTH,
			self.Options.get('max_fact_value_length', DEF_FACT_VALUE_LENGTH)))
		
		# Build our translation table
		self.__trans = '\x00' * 32
		if self.Options['allow_high_ascii']:
			for i in range(32, 256):
				self.__trans += chr(i)
		else:
			for i in range(32, 128):
				self.__trans += chr(i)
			for i in range(128, 256):
				self.__trans += '\x00'
	
	# -----------------------------------------------------------------------
	
	def register(self):
		# Gets are lowest priority (default = 10)
		self.addTextEvent(
			method = self.__Query_Get,
			regexp = re.compile(r'^(?P<name>.+?)\??$'),
			priority = 0,
			help = ('get', '<factoid name>\02?\02 : Ask the bot for the definiton of <factoid name>.'),
		)
		if self.Options.get('public_request', None):
			self.addTextEvent(
				method = self.__Query_Get,
				regexp = re.compile(r'^(?P<name>.+?)\?$'),
				priority = 0,
				IRCTypes = (IRCT_PUBLIC,),
			)
		# Sets aren't much better
		self.addTextEvent(
			method = self.__Query_Set,
			regexp = re.compile(r'^(?!no, +)(?P<name>.+?) +(?<!\\)(is|are) +(?!also +)(?P<value>.+)$'),
			priority = 1,
			help = ('set',  '<factoid name> \02is\02 <whatever> OR <factoid name> \02is also\02 <whatever> : Teach the bot about a topic.'),
		)
		if self.Options.get('public_assignment', None):
			self.addTextEvent(
				method = self.__Query_Set,
				regexp = re.compile(r'^(?!no, +)(?P<name>.+?) +(?<!\\)(is|are) +(?!also +)(?P<value>.+)$'),
				priority = 1,
				IRCTypes = (IRCT_PUBLIC,),
			)
		self.addTextEvent(
			method = self.__Query_Also,
			priority = 2,
			regexp = re.compile(r'^(?P<name>.+?) +(is|are) +also +(?P<value>.+)$'),
		)
		# And the rest are normalish
		self.addTextEvent(
			method = self.__Query_Raw,
			regexp = re.compile(r'^rawfactoid (?P<name>.+?)$'),
			help = ('rawfactoid', "\02rawfactoid\02 <factoid name> : Ask the bot for the definition of <factoid name>. Doesn't do variable substituion or factoid redirection."),
		)
		self.addTextEvent(
			method = self.__Query_No,
			regexp = re.compile(r'^no, +(?P<name>.+?) +(is|are) +(?!also +)(?P<value>.+)$'),
			help = ('overwrite', "\02no,\02 <factoid name> \02is\02 <whatever> : Replace the existing definition of <factoid name> with the new value <whatever>."),
		)
		self.addTextEvent(
			method = self.__Query_Forget,
			regexp = re.compile(r'^forget +(?P<name>.+)$'),
			help = ('forget', '\02forget\02 <factoid name> : Remove a factoid from the bot.'),
		)
		self.addTextEvent(
			method = self.__Query_Replace,
			regexp = re.compile(r'^(?P<name>.+?) +=~ +(?P<modstring>.+)$'),
			help = ('replace', "<factoid name> \02=~ s/\02<search>\02/\02<replace>\02/\02 : Search through the definition of <factoid name>, replacing any instances of the string <search> with <replace>. Note, the '/' characters can be substituted with any other character if either of the strings you are searching for or replacing with contain '/'."),
		)
		self.addTextEvent(
			method = self.__Query_Lock,
			regexp = re.compile(r'^lock +(?P<name>.+)$'),
			help = ('lock', "\02lock\02 <factoid name> : Lock a factoid definition, so most users cannot alter it."),
		)
		self.addTextEvent(
			method = self.__Query_Unlock,
			regexp = re.compile(r'^unlock +(?P<name>.+)$'),
			help = ('unlock', "\02unlock\02 <factoid name> : Unlock a locked factoid definition, so it can be edited by anyone"),
		)
		self.addTextEvent(
			method = self.__Query_Info,
			regexp = re.compile(r'^factinfo +(?P<name>.+)\??$'),
			help = ('factinfo', "\02factinfo\02 <factoid name> : View some statistics about the given factoid."),
		)
		self.addTextEvent(
			method = self.__Query_Status,
			regexp = re.compile(r'^status$'),
			help = ('status', "\02status\02 : Generate some brief stats about the bot."),
		)
		self.addTextEvent(
			method = self.__Query_Tell,
			regexp = re.compile(r'^tell +(?P<nick>.+?) +about +(?P<name>.+)$'),
			help = ('tell', "\02tell\02 <someone> \02about\02 <factoid name> : Ask the bot to send the definition of <factoid name> to <someone> in a /msg."),
		)
		self.addTextEvent(
			method = self.__Query_List_Keys,
			regexp = re.compile(r'^listkeys +(?P<name>.+)$'),
			help = ('listkeys', "\02listkeys\02 <search text> : Search through all the factoid names, and return a list of any that contain <search text>."),
		)
		self.addTextEvent(
			method = self.__Query_List_Values,
			regexp = re.compile(r'^listvalues +(?P<name>.+)$'),
			help = ('listvalues', "\02listvalues\02 <search text> : Search through all the factoid definitions, and return the names of any that contain <search text>."),
		)
	
	# -----------------------------------------------------------------------
	# We're doing the ignore check here, just because it's stupid to have
	# the same ignore check in every single trigger.
	def _message_PLUGIN_TRIGGER(self, message):
		if self.Userlist.Has_Flag(message.data.userinfo, 'SmartyPants', 'ignore'):
			return
		
		Plugin._message_PLUGIN_TRIGGER(self, message)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up a factoid
	def __Query_Get(self, trigger):
		# check to see if it was a public, and abort if we are not replying
		# to public requests for this server/channel
		if trigger.IRCType == IRCT_PUBLIC:
			chans = self.Options.get_net('public_request', trigger)
			if not chans or trigger.target.lower() not in chans:
				return
		
		# Either it wasn't an IRCT_PUBLIC, or we have a config rule that
		# says we are allowed to reply to public queries on this server in
		# this channel, so look it up.
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Get, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up a factoid, but they don't want variable substituion
	# or redirects.
	def __Query_Raw(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Raw, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to set a factoid.
	def __Query_Set(self, trigger):
		name = self.__Sane_Name(trigger)
		
		# check to see if it was a public, and abort if we are not replying
		# to public requests for this server/channel
		if trigger.IRCType == IRCT_PUBLIC:
			chans = self.Options.get_net('public_assignment', trigger)
			if not chans or trigger.target.lower() not in chans:
				return
		
		# dodgy hack to make sure we don't set retarded factoids containing
		# "=~" in them
		if name.find('=~') >= 0:
			return
		
		# Too long
		if len(name) > self.Options['max_fact_name_length']:
			if not trigger.IRCType == IRCT_PUBLIC:
				self.sendReply(trigger, 'Factoid name is too long!')
		else:
			self.dbQuery(trigger, self.__Fact_Set, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Somone wants to replace a factoid definition
	def __Query_No(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_No, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to add to the definition of a factoid
	def __Query_Also(self, trigger):
		name = self.__Sane_Name(trigger)
		if len(name) > self.Options['max_fact_name_length']:
			self.sendReply(trigger, 'Factoid name is too long!')
		else:
			self.dbQuery(trigger, self.__Fact_Also, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to delete a factoid
	def __Query_Forget(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Forget, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a search/replace on a factoid
	def __Query_Replace(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Replace, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to lock a factoid
	def __Query_Lock(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Lock, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to unlock a factoid
	def __Query_Unlock(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Unlock, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants information on a factoid
	def __Query_Info(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Info, INFO_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone asked for our runtime status
	def __Query_Status(self, trigger):
		self.dbQuery(trigger, self.__Fact_Status, STATUS_QUERY)
	
	# -----------------------------------------------------------------------
	# Someone asked to search by key
	def __Query_List_Keys(self, trigger):
		name = self.__Sane_Name(trigger)
		name = name.replace('%', '\%')
		name = name.replace('*', '\*')
		name = name.replace('"', '\\\"')
		name = name.replace("'", "\\\'")
		query =  LISTKEYS_QUERY % name
		self.dbQuery(trigger, self.__Fact_Search, query)
	
	# -----------------------------------------------------------------------
	# Someone asked to search by value
	def __Query_List_Values(self, trigger):
		name = self.__Sane_Name(trigger)
		name = name.replace('%', '\%')
		name = name.replace('*', '\*')
		name = name.replace('"', '\\\"')
		name = name.replace("'", "\\\'")
		query =  LISTVALUES_QUERY % name
		self.dbQuery(trigger, self.__Fact_Search, query)
	
	# -----------------------------------------------------------------------
	# Someone wants us to tell someone else about a factoid
	def __Query_Tell(self, trigger):
		tellnick = trigger.match.group('nick').lower()
		name = self.__Sane_Name(trigger)
		
		if not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'tell'):
			if tellnick[0] in '#&':
				# Target is a channel we're not in.
				if tellnick not in trigger.conn.users.channels():
					self.sendReply(trigger, "I'm not in that channel!")
					tolog = "%s tried to tell %s about '%s', but I'm not in that channel!" % (
						trigger.userinfo, tellnick, name)
					self.putlog(LOG_WARNING, tolog)
					return
				
				# Target is a channel the source isn't in.
				if not trigger.conn.users.in_chan(tellnick, trigger.userinfo.nick):
					self.sendReply(trigger, "You're not in that channel!")
					tolog = "%s tried to tell %s about '%s', but they're not in that channel!" % (
						trigger.userinfo, tellnick, name)
					self.putlog(LOG_WARNING, tolog)
					return
			
			else:
				# Source and target aren't in a common channel
				if not trigger.conn.users.in_same_chan(tellnick, trigger.userinfo.nick):
					self.sendReply(trigger, "That user isn't in a channel with you!")
					tolog = "%s tried to tell %s about '%s', but they're not in a common channel!" % (
						trigger.userinfo, tellnick, name)
					self.putlog(LOG_WARNING, tolog)
					return
		
		self.dbQuery(trigger, self.__Fact_Get, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	# -----------------------------------------------------------------------
	def __Fact_Get(self, trigger, result, redirect=1):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			# The factoid wasn't in our database
			if trigger.IRCType == IRCT_PUBLIC:
				return
			
			self.__dunnos += 1
			
			replytext = random.choice(DUNNO)
			self.sendReply(trigger, replytext)
		
		# Found it!
		else:
			row = result[0]
			value = row['value']
			
			# <null> check
			m = NULL_RE.match(value)
			if m:
				return
			
			# If we have to, check for a redirected factoid
			if redirect:
				m = REDIRECT_RE.match(value)
				if m:
					factoid = self.__Sane_Name(m.group('factoid'))
					# We don't want ones with commas!
					if ',' not in factoid:
						# Not much use going somewhere for an empty redirect
						if factoid  == '':
							replytext = "'%s' redirects to nothing!" % (row['name'])
							self.sendReply(trigger, replytext)
						
						else:
							seen = [row['name']]
							trigger.temp = (seen, factoid)
							self.dbQuery(trigger, self.__Fact_Redirect, GET_QUERY, factoid)
						
						return
			
			# This factoid wasn't a <null>, so update stats and generate the
			# reply
			self.__requests += 1
			
			# This is devinfo (hacked up infobot?) legacy. The factoid database
			# will have a bunch of these, so we might as well support it :|
			#
			# replace "$nick" with the nick of the requester
			escnick = trigger.userinfo.nick.replace('\\', '\\\\')
			value = SUB_NICK_RE.sub(escnick, value)
			
			# replace "$channel" with the target if this was public
			if trigger.IRCType in (IRCT_PUBLIC, IRCT_PUBLIC_D):
				value = SUB_CHAN_RE.sub(trigger.target, value)
			
			# replace "$date" with a shiny date
			datebit = time.strftime('%a %d %b %Y %H:%M:%S')
			shinydate = '%s %s GMT' % (datebit, GetTZ())
			value = SUB_DATE_RE.sub(shinydate, value)
			
			
			# If it's just a get, spit it out
			if trigger.name == '__Query_Get':
				# <reply> and <action> check
				m = REPLY_ACTION_RE.match(value)
				if m:
					typ = m.group('type').lower()
					if typ == 'reply':
						replytext = m.group('value')
					elif typ == 'action':
						replytext = '\x01ACTION %s\x01' % m.group('value')
					self.sendReply(trigger, replytext, process=0)
				
				else:
					replytext = '%s is %s' % (row['name'], value)
					self.sendReply(trigger, replytext)
			
			# If it's really a 'tell', msg the requester and his target
			elif trigger.name == '__Query_Tell':
				tellnick = trigger.match.group('nick')
				
				msgtext = "Told %s that %s is %s" % (tellnick, row['name'], value)
				self.privmsg(trigger.conn, trigger.userinfo.nick, msgtext)
				
				msgtext = "%s wants you to know: %s is %s" % (trigger.userinfo.nick, row['name'], value)
				self.privmsg(trigger.conn, tellnick, msgtext)
			
			
			# Update the request count and nick
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			now = int(time.time())
			self.dbQuery(trigger, None, REQUESTED_QUERY, requester_nick, requester_host, now, name)
	
	# -----------------------------------------------------------------------
	# We've finished looking up a redirected factoid, inform the user.
	# -----------------------------------------------------------------------
	def __Fact_Redirect(self, trigger, result):
		seen, factoid = trigger.temp
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result, redirect failed
		elif result == ():
			# Don't say anything if it was a public request
			if trigger.IRCType == IRCT_PUBLIC:
				return
			
			self.__dunnos += 1
			
			replytext = "'%s' redirects to '%s', which doesn't exist" % (seen[0], factoid)
			self.sendReply(trigger, replytext)
		
		# Result.. yay
		else:
			row = result[0]
			seen.append(row['name'])
			
			# If it's another redirect...
			m = REDIRECT_RE.match(row['value'])
			if m:
				factoid = self.__Sane_Name(m.group('factoid'))
				
				if factoid  == '':
					replytext = "'%s' redirects to nothing!" % (row['name'])
					self.sendReply(trigger, replytext)
				
				# Make sure we're not recursing
				elif factoid in seen:
					redir = ' -> '.join(seen)
					replytext = "'%s' redirects recursively! (%s -> %s)" % (seen[0], redir, factoid)
					self.sendReply(trigger, replytext)
				
				# Don't redirect more than 5 times
				else:
					if len(seen) < 5:
						trigger.temp = (seen, factoid)
						self.dbQuery(trigger, self.__Fact_Redirect, GET_QUERY, factoid)
					
					else:
						replytext = "'%s' redirects too many times!" % (seen[0])
						self.sendReply(trigger, replytext)
			
			# Otherwise, do the normal GET stuff
			else:
				self.__Fact_Get(trigger, result, redirect=0)
	
	# -----------------------------------------------------------------------
	# A user just tried to set a factoid.. if it doesn't already exist, we
	# will go ahead and add it.
	def __Fact_Set(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result, insert it
		elif result == ():
			value = trigger.match.group('value')
			if len(value) > self.Options['max_fact_value_length']:
				self.sendReply(trigger, 'Factoid value is too long!')
				return
			
			self.__sets += 1
			author_nick = trigger.userinfo.nick
			author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			created_time = int(time.time())
			self.dbQuery(trigger, self.__Query_INSERT, SET_QUERY, name, value, author_nick, author_host, created_time)
		
		# It was already in our database
		else:
			if trigger.IRCType == IRCT_PUBLIC:
				return
			
			row = result[0]
			replytext = "...but '%s' is already set to something else!" % row['name']
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# something
	# -----------------------------------------------------------------------
	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	# -----------------------------------------------------------------------
	def __Fact_Raw(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			# The factoid wasn't in our database
			self.__dunnos += 1
			
			replytext = random.choice(DUNNO)
			self.sendReply(trigger, replytext)
		
		# Found it!
		else:
			row = result[0]
			
			# This factoid wasn't a <null>, so update stats and generate the
			# reply
			self.__requests += 1
			
			replytext = '%(name)s is %(value)s' % row
			self.sendReply(trigger, replytext)
			
			# Update the request count and nick
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			now = int(time.time())
			self.dbQuery(trigger, None, REQUESTED_QUERY, requester_nick, requester_host, now, name)
	
	# -----------------------------------------------------------------------
	# A user just tried to update a factoid by replacing the existing
	# definition with a new one
	def __Fact_No(self, trigger, result):
		name = self.__Sane_Name(trigger)
		value = trigger.match.group('value')
		if len(value) > self.Options['max_fact_value_length']:
			replytext = 'Factoid value is too long!'
			self.sendReply(trigger, replytext)
			return
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result, insert it
		elif result == ():
			self.__sets += 1
			author_nick = trigger.userinfo.nick
			author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			created_time = int(time.time())
			self.dbQuery(trigger, self.__Query_INSERT, SET_QUERY, name, value, author_nick, author_host, created_time)
		
		# It was in our database, ruh-roh
		else:
			# The user will need the delete flag to replace factoids
			if not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'delete'):
				replytext = "You don't have permission to overwrite factoids"
				self.sendReply(trigger, replytext)
				return
			
			# If it's locked, make sure the user has the lock flag
			row = result[0]
			if row['locker_nick'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You don't have permission to alter locked factoids.")
				return
			
			self.__modifys += 1
			
			author_nick = trigger.userinfo.nick
			author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			created_time = int(time.time())
			self.dbQuery(trigger, self.__Query_UPDATE, NO_QUERY, value, author_nick, author_host, created_time, name)
	
	# -----------------------------------------------------------------------
	# A user just tried to update a factoid by appending more data. If it
	# exists, we add to it's definition, otherwise we make a new factoid.
	def __Fact_Also(self, trigger, result):
		name = self.__Sane_Name(trigger)
		value = trigger.match.group('value')
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result, insert it (cheat a bit)
		elif result == ():
			self.__Fact_Set(trigger, result)
		
		# Already in our database
		else:
			row = result[0]
			
			if self.Options['alter_is_also'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'alter'):
				replytext = "You don't have permission to alter factoids."
				self.sendReply(trigger, replytext)
				return
			if row['locker_nick'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You are not allowed to alter locked factoids.")
				return
			
			new_value = "%s, or %s" % (row['value'], value)
			self.__Fact_Update(trigger, new_value)
	
	# -----------------------------------------------------------------------
	# Update a factoid by changing the value text
	def __Fact_Update(self, trigger, value):
		name = self.__Sane_Name(trigger)
		if len(value) > self.Options['max_fact_value_length']:
			replytext = "Factoid value is too long!"
			self.sendReply(trigger, replytext)
			return
		
		self.__modifys += 1
		modified_time = int(time.time())
		modifier_nick = trigger.userinfo.nick
		modifier_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
		self.dbQuery(trigger, self.__Query_UPDATE, MOD_QUERY, value, modifier_nick, modifier_host, modified_time, name)
	
	# -----------------------------------------------------------------------
	# Someone asked to delete a factoid. Check their flags to see if they are
	# allowed to, then delete or refuse.
	def __Fact_Forget(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
			self.sendReply(trigger, replytext)
		
		# It was in our database, delete it!
		else:
			row = result[0]
			if row['locker_nick']:
				replytext = "The factoid '%s' is locked, unlock it before deleting." % name
				self.sendReply(trigger, replytext)
				return
			
			if not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'delete'):
				replytext = "You don't have permission to delete factoids."
				self.sendReply(trigger, replytext)
				return
			
			self.__dels += 1
			self.dbQuery(trigger, self.__Query_DELETE, FORGET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# A user just tried to do a search/replace on a factoid.
	def __Fact_Replace(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
			self.sendReply(trigger, replytext)
		
		# It was in our database, modify it!
		else:
			row = result[0]
			value = row['value']
			
			if self.Options['alter_search_replace'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'alter'):
				replytext = "You don't have permission to alter factoids."
				self.sendReply(trigger, replytext)
				return
			if row['locker_nick'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You don't have permission to alter locked factoids.")
				return
			
			modstring = trigger.match.group('modstring')
			if modstring.startswith("s"):
				# break the modstring into its components
				bits = modstring.split(modstring[1])
				if len(bits) == 4:
					search = bits[1]
					replace = bits[2]
					
					new_value = value.replace(search, replace, 1)
					if new_value == value:
						replytext = "That doesn't contain '%s'" % search
						self.sendReply(trigger, replytext)
						return
					
					# bitch at the user if they made the factoid too
					# long
					if len(new_value) > self.Options['max_fact_value_length']:
						self.sendReply(trigger, 'Factoid value is too long!')
					else:
						# everything is okay, make the change
						self.__Fact_Update(trigger, new_value)
				
				# we got a junk modstring
				else:
					replytext = "'%s' is not a valid search/replace string." % modstring
					self.sendReply(trigger, replytext)
			
			else:
				replytext = "'%s' is not a valid search/replace string." % modstring
				self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# A user just tried to lock a factoid.
	# Check to make sure that they have the appropriate access, then
	# either lock the factoid or tell them to get lost
	def __Fact_Lock(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
			self.sendReply(trigger, replytext)
		
		# It was in our database, lock it!
		else:
			row = result[0]
			
			# See if the factoid is already locked
			if row['locker_nick']:
				replytext = "Factoid '%s' was already locked by %s!" % (name, row['locker_nick'])
				self.sendReply(trigger, replytext)
				return
			
			# Check user permissions
			if not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You don't have permission to lock factoids.")
				return
			
			# Lock it
			locker_nick = trigger.userinfo.nick
			locker_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
			locked_time = int(time.time())
			self.dbQuery(trigger, self.__Query_UPDATE, LOCK_QUERY, locker_nick, locker_host, locked_time, name)
	
	# -----------------------------------------------------------------------
	# A user just tried to unlock a factoid. Check to make sure that they have
	# the appropriate access, then either unlock the factoid or tell them to
	# get lost.
	def __Fact_Unlock(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
			self.sendReply(trigger, replytext)
		
		# It was in our database, lock it!
		else:
			row = result[0]
			# See if the factoid is even locked
			if not row['locker_nick']:
				replytext = "Factoid '%s' is not locked!" % name
				self.sendReply(trigger, replytext)
				return
			
			# Check user permissions
			if not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You don't have permission to lock factoids.")
				return
			
			# Unlock it
			self.dbQuery(trigger, self.__Query_UPDATE, UNLOCK_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone asked for some info on a factoid.
	def __Fact_Info(self, trigger, result):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
		
		# A result!
		else:
			now = int(time.time())
			row = result[0]
			
			parts = []
			
			# Created info
			part = '%s -- created by %s (%s), %s ago' % (name, row['author_nick'],
				row['author_host'], NiceTime(now, row['created_time']))
			parts.append(part)
			
			# Requested info
			if row['request_count']:
				part = 'requested %s time(s), last by %s, %s ago' % (row['request_count'],
					row['requester_nick'], NiceTime(now, row['requested_time']))
				parts.append(part)
			# Modified info
			if row['modifier_nick']:
				part = 'last modified by %s (%s), %s ago' % (row['modifier_nick'],
					row['modifier_host'], NiceTime(now, row['modified_time']))
				parts.append(part)
			# Lock info
			if row['locker_nick']:
				part = 'locked by %s (%s), %s ago' % (row['locker_nick'], row['locker_host'],
					NiceTime(now, row['locked_time']))
				parts.append(part)
			
			# Put it back together
			replytext = '; '.join(parts)
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone just asked for our status
	def __Fact_Status(self, trigger, result):
		num = int(result[0]['total'])
		replytext = "Since %s, there have been \02%d\02 requests, \02%d\02 modifications, \02%d\02 new factoids, \02%d\02 deletions, and \02%d\02 dunnos. I currently reference \02%d\02 factoids." % (self.__start_time, self.__requests, self.__modifys, self.__sets, self.__dels, self.__dunnos, num)
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone just asked to search the factoid database
	def __Fact_Search(self, trigger, result):
		findme = self.__Sane_Name(trigger)
		if trigger.name == '__Query_List_Keys':
			what = 'key'
		elif trigger.name == '__Query_List_Values':
			what = 'value'
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "Factoid search of '\02%s\02' by %s returned no results." % (findme, what)
			self.sendReply(trigger, replytext)
		
		# Some results!
		else:
			# Too many!
			if len(result) > MAX_FACT_SEARCH_RESULTS:
				replytext = "Factoid search of '\02%s\02' by %s yielded too many results (%d). Please refine your query." % (findme, what, len(result))
			# Enough
			else:
				replytext = "Factoid search of '\02%s\02' by %s (\02%d\02 results): " % (findme, what, len(result))
				
				names = [row['name'] for row in result]
				replytext += ' \02;;\02 '.join(names)
			
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	def __Query_Handle(self, trigger, result, thing):
		# Error!
		if result is None:
			replytext = 'An unknown database error occurred.'
		
		# Insert failed
		elif result == 0:
			replytext = 'Factoid %s failed, eek!' % thing
		
		# Insert succeeded
		elif result == 1:
			if trigger.IRCType == IRCT_PUBLIC:
				return
			replytext = random.choice(OK)
		
		self.sendReply(trigger, replytext)
	
	# Handle the DELETE reply
	def __Query_DELETE(self, trigger, result):
		self.__Query_Handle(trigger, result, 'deletion')
	
	# Handle the INSERT reply
	def __Query_INSERT(self, trigger, result):
		self.__Query_Handle(trigger, result, 'insertion')
	
	# Handle the UPDATE reply
	def __Query_UPDATE(self, trigger, result):
		self.__Query_Handle(trigger, result, 'modification')
	
	# -----------------------------------------------------------------------
	# Return a sanitised factoid name.
	def __Sane_Name(self, trigger):
		# If it's just a string, use it instead
		if type(trigger) in types.StringTypes:
			newname = trigger
		else:
			newname = trigger.match.group('name')
		
		# lower case
		newname = newname.lower()
		# translate the name according to our table
		newname = newname.translate(self.__trans)
		# remove any bad chars now
		newname = newname.replace('\x00', '')
		
		# un-escape escaped is/are
		newname = newname.replace('\\is', 'is')
		newname = newname.replace('\\are', 'are')
		
		return newname

# -----------------------------------------------------------------------
# Turn an amount of seconds into a nice understandable string
# -----------------------------------------------------------------------
def NiceTime(now, seconds):
	parts = []
	
	if seconds < 1000:
		return 'a long time'
	
	# 365.242199 days in a year, according to Google
	years, seconds = divmod(now - seconds, 31556926)
	days, seconds = divmod(seconds, 86400)
	hours, seconds = divmod(seconds, 3600)
	minutes, seconds = divmod(seconds, 60)
	
	# a year
	if years:
		part = '%dy' % years
		parts.append(part)
	# a day
	if days:
		part = '%dd' % days
		parts.append(part)
	# an hour
	if hours:
		part = '%dh' % hours
		parts.append(part)
	# a minute
	if minutes:
		part = '%dm' % minutes
		parts.append(part)
	# any leftover seconds
	if seconds:
		part = '%ds' % seconds
		parts.append(part)
	
	# If we have any stuff, return it
	if parts:
		return ' '.join(parts)
	else:
		return '0s'
