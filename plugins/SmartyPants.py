# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'An implementation of an infobot, similar to... every other infobot.'

import copy
import random
import re
import time

from classes.Plugin import *
from classes.Common import *
from classes.Constants import *

# ---------------------------------------------------------------------------

FACT_SET = "FACT_SET"
FACT_GET = "FACT_GET"
FACT_REDIRECT = "FACT_REDIRECT"
FACT_ALSO = "FACT_ALSO"
FACT_DEL = "FACT_DEL"
FACT_REPLACE = "FACT_REPLACE"
FACT_NO = "FACT_NO"
FACT_INFO = "FACT_INFO"
FACT_STATUS = "FACT_STATUS"
FACT_LOCK = "FACT_LOCK"
FACT_UNLOCK = "FACT_UNLOCK"
FACT_LISTKEYS = "FACT_LISTKEYS"
FACT_LISTVALUES = "FACT_LISTVALUES"
FACT_TELL = "FACT_TELL"

FACT_UPDATEDB = "FACT_MOD"

GET_QUERY = "SELECT name, value, locker_nick FROM factoids WHERE name = %s"
SET_QUERY = "INSERT INTO factoids (name, value, author_nick, author_host, created_time) VALUES (%s, %s, %s, %s, %s)"
MOD_QUERY = "UPDATE factoids SET value = %s, modifier_nick = %s, modifier_host = %s, modified_time = %s WHERE name = %s"
DEL_QUERY = "DELETE FROM factoids WHERE name = %s"
INFO_QUERY = "SELECT * FROM factoids WHERE name = %s"

# Build the giant 'no, ' query
NO_QUERY  = "UPDATE factoids SET value = %s, author_nick = %s, author_host = %s, created_time = %s"
NO_QUERY += ", modifier_nick = '', modifier_host = '', modified_time = NULL, requester_nick = ''"
NO_QUERY += ", requester_host = '', requested_time = NULL, request_count = 0, locker_nick = ''"
NO_QUERY += ", locker_host = '', locked_time = NULL WHERE name = %s"

REQUESTED_QUERY = "UPDATE factoids SET request_count = request_count + 1, requester_nick = %s, requester_host = %s, requested_time = %s WHERE name = %s"

LOCK_QUERY = "UPDATE factoids SET locker_nick = %s, locker_host = %s, locked_time = %s WHERE name = %s"
UNLOCK_QUERY = "UPDATE factoids SET locker_nick = NULL, locker_host = NULL, locked_time = NULL WHERE name = %s"

STATUS_QUERY = "SELECT count(*) AS total FROM factoids"

LISTKEYS_QUERY = "SELECT name FROM factoids WHERE name LIKE '%%%s%%'"
LISTVALUES_QUERY = "SELECT name FROM factoids WHERE value LIKE '%%%s%%'"

GET_D_RE = re.compile(r'^(?P<name>.+?)\??$')
GET_RE = re.compile(r'^(?P<name>.+?)\?$')
SET_RE = re.compile(r'^(?!no, +)(?P<name>.+?) +(?<!\\)(is|are) +(?!also +)(?P<value>.+)$')
NO_RE = re.compile(r'^no, +(?P<name>.+?) +(is|are) +(?!also +)(?P<value>.+)$')
ALSO_RE = re.compile(r'^(?P<name>.+?) +(is|are) +also +(?P<value>.+)$')
DEL_RE = re.compile(r'^forget +(?P<name>.+)$')
REPLACE_RE = re.compile(r'^(?P<name>.+?) +=~ +(?P<modstring>.+)$')
LOCK_RE = re.compile(r'^lock +(?P<name>.+)$')
UNLOCK_RE = re.compile(r'^unlock +(?P<name>.+)$')
INFO_RE = re.compile(r'^factinfo +(?P<name>.+)\??$')
STATUS_RE = re.compile(r'^status$')
LISTKEYS_RE = re.compile(r'^listkeys +(?P<name>.+)$')
LISTVALUES_RE = re.compile(r'^listvalues +(?P<name>.+)$')
TELL_RE = re.compile(r'^tell +(?P<nick>.+?) +about +(?P<name>.+)$')

REPLY_ACTION_RE = re.compile(r'^<(?P<type>reply|action)>\s*(?P<value>.+)$', re.I)
NULL_RE = re.compile(r'^<null>\s*$', re.I)

# match redirected factoids
REDIRECT_RE = re.compile(r'^see(: *| +)(?P<factoid>.+)$')

# ---------------------------------------------------------------------------

MAX_FACT_NAME_LENGTH = 32
MAX_FACT_VAL_LENGTH = 455
MAX_FACT_SEARCH_RESULTS = 40

# ---------------------------------------------------------------------------

OK = [
	"OK",
	"you got it",
	"done",
	"okay",
	"okie",
	"as you wish",
	"by your command"
]

DUNNO = [
	"no idea",
	"I don't know",
	"you got me",
	"not a clue",
	"nfi",
	"I dunno"
]

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
	
	# -----------------------------------------------------------------------
	
	def setup(self):
		self.__start_time = time.asctime()
		self.__requests = 0
		self.__dunnos = 0
		self.__sets = 0
		self.__modifys = 0
		self.__dels = 0
		
		self.__setup_config()
		
		# build our translation string
		self.__Build_Translation()
	
	def rehash(self):
		self.__setup_config()
	
	def __setup_config(self):
		self.__get_pub = {}
		self.__set_pub = {}
		
		for option in self.Config.options('Infobot'):
			try:
				[text, network] = option.split('.')
				network = network.lower()
			except:
				tolog = "malformed option in Infobot config: %s" % option
				self.putlog(LOG_WARNING, tolog)
			else:
				if text == 'public_request':
					self.__get_pub[network] = self.Config.get('Infobot', option).lower().split()
				elif text == 'public_assignment':
					self.__set_pub[network] = self.Config.get('Infobot', option).lower().split()
				else:
					tolog = "malformed option in Infobot config: %s" % option
					self.putlog(LOG_WARNING, tolog)
	
	def __Build_Translation(self):
		# space # ' - . [ ] ^ _ |
		chars = [32, 35, 39, 45, 46, 91, 93, 94, 95, 124]
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
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		# Gets are lowest priority (default = 10)
		self.setTextEventPriority(0, FACT_GET, GET_D_RE, IRCT_PUBLIC_D, IRCT_MSG)
		if self.__get_pub:
			self.setTextEventPriority(0, FACT_GET, GET_RE, IRCT_PUBLIC)
		# Sets aren't much better
		self.setTextEventPriority(1, FACT_SET, SET_RE, IRCT_PUBLIC_D, IRCT_MSG)
		if self.__set_pub:
			self.setTextEventPriority(1, FACT_SET, SET_RE, IRCT_PUBLIC)
		# Rest are normal
		self.setTextEvent(FACT_NO, NO_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_ALSO, ALSO_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_DEL, DEL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_REPLACE, REPLACE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_LOCK, LOCK_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_UNLOCK, UNLOCK_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_INFO, INFO_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_STATUS, STATUS_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_LISTKEYS, LISTKEYS_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_LISTVALUES, LISTVALUES_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FACT_TELL, TELL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		
		self.registerEvents()
		
		self.__set_help_messages()
	
	# -----------------------------------------------------------------------

	def __set_help_messages(self):
		FACT_GET_HELP = "'<factoid name>\02?\02' : Ask the bot for the definiton of <factoid name>."
		FACT_SET_HELP = "'<factoid name> \02is\02 <whatever>' OR '<factoid name> \02is also\02 <whatever> : Teach the bot about a topic."
		FACT_MOD_HELP = "'<factoid name> \02=~ s/\02<search>\02/\02<replace>\02/\02' : Search through the definition of <factoid name>, replacing any instances of the string <search> with <replace>. Note, the '/' characters can be substituted with any other character if either of the strings you are searching for or replacing with contain '/'."
		FACT_OVERWRITE_HELP = "'\02no,\02 <factoid name> \02is\02 <whatever>' : Replace the existing definition of <factoid name> with the new value <whatever>."
		FACT_FORGET_HELP = "'\02forget\02 <factoid name>' : Remove a factoid from the bot."
		FACT_LOCK_HELP = "'\02lock\02 <factoid name>' : Lock a factoid definition, so most users cannot alter it."
		FACT_UNLOCK_HELP = "'\02unlock\02 <factoid name>' : Unlock a locked factoid definition, so it can be edited by anyone"
		FACT_LISTKEYS_HELP = "'\02listkeys\02 <search text>' : Search through all the factoid names, and return a list of any that contain <search text>"
		FACT_LISTVALUES_HELP = "'\02listvalues\02 <search text>' : Search through all the factoid definitions, and return the names of any that contain <search text>"
		FACT_STATUS_HELP = "'\02status\02' : Generate some brief stats about the bot."
		FACT_TELL_HELP = "'\02tell\02 <someone> \02about\02 <factoid name>' : Ask the bot to send the definition of <factoid name> to <someone> in a /msg."
		FACT_INFO_HELP = "'\02factinfo\02 <factoid name>' : View some statistics about the given factoid."
		
		self.setHelp('infobot', 'get', FACT_GET_HELP)
		self.setHelp('infobot', 'set', FACT_SET_HELP)
		self.setHelp('infobot', '=~', FACT_MOD_HELP)
		self.setHelp('infobot', 'overwrite', FACT_OVERWRITE_HELP)
		self.setHelp('infobot', 'forget', FACT_FORGET_HELP)
		self.setHelp('infobot', 'lock', FACT_LOCK_HELP)
		self.setHelp('infobot', 'unlock', FACT_UNLOCK_HELP)
		self.setHelp('infobot', 'tell', FACT_TELL_HELP)
		self.setHelp('infobot', 'listkeys', FACT_LISTKEYS_HELP)
		self.setHelp('infobot', 'listvalues', FACT_LISTVALUES_HELP)
		self.setHelp('infobot', 'factinfo', FACT_INFO_HELP)
		self.setHelp('infobot', 'status', FACT_STATUS_HELP)
		
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# We're doing the ignore check here, just because it's stupid to have
	# the same ignore check in every single trigger.
	def _message_PLUGIN_TRIGGER(self, message):
		if self.Userlist.Has_Flag(message.data.userinfo, 'SmartyPants', 'ignore'):
			return
		
		Plugin._message_PLUGIN_TRIGGER(self, message)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up a factoid
	def _trigger_FACT_GET(self, trigger):
		# check to see if it was a public, and abort if we are not replying
		# to public requests for this server/channel
		if trigger.event.IRCType == IRCT_PUBLIC:
			network = trigger.conn.options['name'].lower()
			try:
				if trigger.target.lower() not in self.__get_pub[network]:
					return
			except:
				return
		
		# Either it wasn't an IRCT_PUBLIC, or we have a config rule that
		# says we are allowed to reply to public queries on this server in
		# this channel, so look it up.
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Get, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to set a factoid.
	def _trigger_FACT_SET(self, trigger):
		name = self.__Sane_Name(trigger)
		
		# check to see if it was a public, and abort if we are not replying
		# to public requests for this server/channel
		if trigger.event.IRCType == IRCT_PUBLIC:
			network = trigger.conn.options['name'].lower()
			try:
				if trigger.target.lower() not in self.__set_pub[network]:
					return
			except:
				return
		
		# dodgy hack to make sure we don't set retarded factoids containing
		# "=~" in them
		if name.find('=~') >= 0:
			return
		
		# Too long
		if len(name) > MAX_FACT_NAME_LENGTH:
			if not trigger.event.IRCType == IRCT_PUBLIC:
				self.sendReply(trigger, 'Factoid name is too long!')
		else:
			self.dbQuery(trigger, self.__Fact_Set, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Somone wants to replace a factoid definition
	def _trigger_FACT_NO(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_No, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to add to the definition of a factoid
	def _trigger_FACT_ALSO(self, trigger):
		name = self.__Sane_Name(trigger)
		if len(name) > MAX_FACT_NAME_LENGTH:
			self.sendReply(trigger, 'Factoid name is too long!')
		else:
			self.dbQuery(trigger, self.__Fact_Also, GET_QUERY, name)
		
	# -----------------------------------------------------------------------
	# Someone wants to delete a factoid
	def _trigger_FACT_DEL(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Del, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a search/replace on a factoid
	def _trigger_FACT_REPLACE(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Replace, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to lock a factoid
	def _trigger_FACT_LOCK(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Lock, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants to unlock a factoid
	def _trigger_FACT_UNLOCK(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Unlock, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone wants information on a factoid
	def _trigger_FACT_INFO(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Info, INFO_QUERY, name)
	
	# -----------------------------------------------------------------------
	# Someone asked for our runtime status
	def _trigger_FACT_STATUS(self, trigger):
		self.dbQuery(trigger, self.__Fact_Status, STATUS_QUERY)
	
	# -----------------------------------------------------------------------
	# Someone asked to search by key
	def _trigger_FACT_LISTKEYS(self, trigger):
		name = self.__Sane_Name(trigger)
		name = name.replace("%", "\%")
		name = name.replace('"', '\\\"')
		name = name.replace("'", "\\\'")
		query =  LISTKEYS_QUERY % name
		self.dbQuery(trigger, self.__Fact_Search, query)
	
	# -----------------------------------------------------------------------
	# Someone asked to search by value
	def _trigger_FACT_LISTVALUES(self, trigger):
		name = self.__Sane_Name(trigger)
		name = name.replace("%", "\%")
		name = name.replace('"', '\\\"')
		name = name.replace("'", "\\\'")
		query =  LISTVALUES_QUERY % name
		self.dbQuery(trigger, self.__Fact_Search, query)
	
	# -----------------------------------------------------------------------
	# Someone wants us to tell someone else about a factoid
	def _trigger_FACT_TELL(self, trigger):
		name = self.__Sane_Name(trigger)
		self.dbQuery(trigger, self.__Fact_Tell, GET_QUERY, name)
	
	# -----------------------------------------------------------------------
	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	# -----------------------------------------------------------------------
	def __Fact_Get(self, trigger, result, redirect=1):
		name = self.__Sane_Name(trigger)
		
		# Error!
		if result is None:
			self.sendReply('An unknown database error occurred.')
		
		# No result
		elif result == ():
			# The factoid wasn't in our database
			if trigger.event.IRCType == IRCT_PUBLIC:
				return
			
			self.__dunnos += 1
			
			replytext = random.choice(DUNNO)
			self.sendReply(trigger, replytext)
		
		# Found it!
		else:
			row = result[0]
			
			# <null> check
			m = NULL_RE.match(row['value'])
			if m:
				return
			
			# If we have to, check for a redirected factoid
			if redirect:
				m = REDIRECT_RE.match(row['value'])
				if m:
					factoid = m.group('factoid')
					trigger.temp = (row['name'], factoid)
					self.dbQuery(trigger, self.__Fact_Redirect, GET_QUERY, factoid)
					return
			
			# This factoid wasn't a <null>, so update stats and generate the
			# reply
			self.__requests += 1
			
			# XXX This is devinfo legacy, I'm not really sure I want to do this
			# but the factoid database will have a bunch of factoids that
			# expect this behaviour
			# replace "$nick" with the nick of the guy that requested this
			# factoid
			row['value'] = re.sub(r'(?P<c>[^\\]|^)\$nick', \
				'\g<c>' + trigger.userinfo.nick, row['value'])
			#row['value'] = row['value'].replace('$nick', trigger.userinfo.nick)
			
			# replace "$channel" with the target if this was public
			if trigger.event.IRCType in (IRCT_PUBLIC, IRCT_PUBLIC_D):
				row['value'] = re.sub(r'(?P<c>[^\\]|^)\$channel', \
					'\g<c>' + trigger.target, row['value'])
				#row['value'] = row['value'].replace('$channel', trigger.target)
				
			# replace "$date" with a shiny date
			datebit = time.strftime('%a %d %b %Y %H:%M:%S')
			shinydate = '%s %s GMT' % (datebit, GetTZ())
			row['value'] = re.sub(r'(?P<c>[^\\]|^)\$date', \
				'\g<c>' + shinydate, row['value'])
			#row['value'] = row['value'].replace('$date', shinydate)
			
			# <reply> and <action> check
			m = REPLY_ACTION_RE.match(row['value'])
			if m:
				typ = m.group('type').lower()
				if typ == 'reply':
					replytext = m.group('value')
				elif typ == 'action':
					replytext = '\x01ACTION %s\x01' % m.group('value')
				self.sendReply(trigger, replytext, process=0)
			
			else:
				replytext = '%(name)s is %(value)s' % row
				self.sendReply(trigger, replytext)
			
			# Update the request count and nick
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			now = int(time.time())
			self.dbQuery(trigger, None, REQUESTED_QUERY, requester_nick, requester_host, now, name)
	
	# -----------------------------------------------------------------------
	# We've finished looking up a redirected factoid, inform the user.
	# -----------------------------------------------------------------------
	def __Fact_Redirect(self, trigger, result):
		# Error!
		if result is None:
			self.sendReply('An unknown database error occurred.')
		
		# No result, redirect failed
		elif result == ():
			# Don't say anything if it was a public request
			if trigger.event.IRCType == IRCT_PUBLIC:
				return
			
			self.__dunnos += 1
			
			replytext = "'%s' redirects to '%s', which doesn't exist" % trigger.temp
			self.sendReply(trigger, replytext)
		
		# Result.. yay
		else:
			row = result[0]
			
			# If it's another redirect, give up
			m = REDIRECT_RE.match(row['value'])
			if m:
				replytext = "'%s' redirects too many times!" % trigger.temp[0]
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
			self.sendReply('An unknown database error occurred.')
		
		# No result, insert it
		elif result == ():
			value = trigger.match.group('value')
			if len(value) > MAX_FACT_VAL_LENGTH:
				self.sendReply(trigger, 'Factoid value is too long!')
				return
			
			self.__sets += 1
			author_nick = trigger.userinfo.nick
			author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			created_time = int(time.time())
			self.dbQuery(trigger, self.__Query_INSERT, SET_QUERY, name, value, author_nick, author_host, created_time)
		
		# It was already in our database
		else:
			if trigger.event.IRCType == IRCT_PUBLIC:
				return
			
			row = result[0]
			replytext = "...but '%s' is already set to something else!" % row['name']
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# A user just tried to update a factoid by replacing the existing
	# definition with a new one
	def __Fact_No(self, trigger, result):
		name = self.__Sane_Name(trigger)
		value = trigger.match.group('value')
		if len(value) > MAX_FACT_VAL_LENGTH:
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
			if row['locker_nick'] and not self.Userlist.Has_Flag(trigger.userinfo, 'SmartyPants', 'lock'):
				self.sendReply(trigger, "You are not allowed to alter locked factoids.")
				return
			
			new_value = "%s, or %s" % (row['value'], value)
			self.__Fact_Update(trigger, new_value)
	
	# -----------------------------------------------------------------------
	# Update a factoid by changing the value text
	def __Fact_Update(self, trigger, value):
		name = self.__Sane_Name(trigger)
		if len(value) > MAX_FACT_VAL_LENGTH:
			replytext = "Factoid value is too long!"
			self.sendReply(trigger, replytext)
			return
		
		self.__modifys += 1
		modified_time = int(time.time())
		modifier_nick = trigger.userinfo.nick
		modifier_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
		self.dbQuery(trigger, self.__Query_UPDATE, MOD_QUERY, value, modifier_nick, modifier_host, modified_time, name)
	
	# -----------------------------------------------------------------------
	# Someone asked to delete a factoid.
	# Check their flags to see if they have permission, then delete or refuse
	def __Fact_Del(self, trigger, result):
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
			self.dbQuery(trigger, self.__Query_DELETE, DEL_QUERY, name)
	
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
					if len(new_value) > MAX_FACT_VAL_LENGTH:
						self.sendReply(trigger, 'Factoid value is too long!')
					else:
						# everything is okay, make the change
						self.__Fact_Update(trigger, new_value)
					
					# The following code is an alternative to the above
					# block, starting from new_value = ...
					# This code allows for arbitrary regexps in the
					# search/replace string, instead of just words.
					# I've commented this out and replaced it with the
					# above code because I'm not sure we should let
					# people on irc do this sort of thing, since it is
					# quite easy to get a regexp wrong and destroy an
					# entire factoid.
					#
					#try:
					#	s = re.compile(search)
					#except:
					#	replytext = "'%s is not a valid regexp" % search
					#	self.sendReply(trigger, replytext)
					#else:
					#	new_value = re.sub(s, replace, value)
					#	if len(new_value) > MAX_FACT_VAL_LENGTH:
					#		replytext = "that will make the factoid too long"
					#		self.sendReply(trigger, replytext)
					#	else:
					#		# make the changes!
					#		self.__Fact_Update(trigger, new_value)
				
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
			row = result[0]
			
			now = int(time.time())
			then = row['created_time']
			row['created_time'] = self.__Nice_Time(now - then)
			
			text = '%(name)s -- created by %(author_nick)s (%(author_host)s), %(created_time)s ago'
			if row['request_count']:
				then = row['requested_time']
				row['requested_time'] = self.__Nice_Time(now - then)
				text += '; requested %(request_count)d time(s), last by %(requester_nick)s, %(requested_time)s ago'
			if row['modifier_nick']:
				then = row['modified_time']
				row['modified_time'] = self.__Nice_Time(now - then)
				text += '; last modified by %(modifier_nick)s (%(modifier_host)s), %(modified_time)s ago'
			if row['locker_nick']:
				then = row['locked_time']
				row['locked_time'] = self.__Nice_Time(now - then)
				text += '; locked by %(locker_nick)s (%(locker_host)s), %(locked_time)s ago'
			
			replytext = text % row
		
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
		if trigger.name == FACT_LISTKEYS:
			what = 'key'
		elif trigger.name == FACT_LISTVALUES:
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
	# Someone wants us to tell someone else about a factoid!
	def __Fact_Tell(self, trigger, result):
		name = self.__Sane_Name(trigger)
		tellnick = trigger.match.group('nick')
		
		# Error!
		if result is None:
			self.sendReply(trigger, 'An unknown database error occurred.')
		
		# No result
		elif result == ():
			replytext = "No such factoid: '%s'" % name
		
		# A result!
		else:
			self.__requests += 1
			row = result[0]
			value = row['value']
			
			# We have to do a bit of hackery here.. we always send two /msgs in
			# reply to this event; one to the guy being told, and one to the
			# guy that triggered the event confirming that we have performed
			# the telling
			trigger.event.IRCType = IRCT_MSG
			replytext = "Told %s that %s is %s" % (tellnick, name, value)
			self.sendReply(trigger, replytext)
			
			dupe = copy.copy(trigger)
			dupe.userinfo = copy.deepcopy(trigger.userinfo)
			replytext = "%s wants you to know: %s is %s" % (trigger.userinfo.nick, name, value)
			dupe.userinfo.nick = tellnick
			self.sendReply(dupe, replytext)
			
			# update our stats in the db
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			now = int(time.time())
			self.dbQuery(trigger, None, REQUESTED_QUERY, requester_nick, requester_host, now, name)
	
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
			if trigger.event.IRCType == IRCT_PUBLIC:
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
		# lower case
		newname = trigger.match.group('name').lower()
		# translate the name according to our table
		newname = newname.translate(self.__trans)
		# remove any bad chars now
		newname = newname.replace('\x00', '')
		
		# un-escape escaped is/are
		newname = newname.replace('\\is', 'is')
		newname = newname.replace('\\are', 'are')
		
		return newname
	
	# -----------------------------------------------------------------------
	# Turn an amount of seconds into a nice string detailing how long it
	# is in english
	# -----------------------------------------------------------------------
	def __Nice_Time(self, seconds):
		parts = []
		
		years, seconds = divmod(seconds, 31536000)
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
			return 'right now?'

# ---------------------------------------------------------------------------
