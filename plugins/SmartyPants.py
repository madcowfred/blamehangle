#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains the factoid resolver.

import copy
import random
import re
import time
import types

from classes.Plugin import *
from classes.Common import *
from classes.Constants import *
from classes.Users import *

# ---------------------------------------------------------------------------

FACT_SET = "FACT_SET"
FACT_GET = "FACT_GET"
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

REQUESTED_QUERY = "UPDATE factoids SET request_count = request_count + 1, requester_nick = %s, requester_host = %s, requested_time = %s WHERE name = %s"

LOCK_QUERY = "UPDATE factoids SET locker_nick = %s, locker_host = %s, locked_time = %s WHERE name = %s"
UNLOCK_QUERY = "UPDATE factoids SET locker_nick = NULL, locker_host = NULL, locked_time = NULL WHERE name = %s"

STATUS_QUERY = "SELECT count(*) AS total FROM factoids"

LISTKEYS_QUERY = "SELECT name FROM factoids WHERE name LIKE '%%%s%%'"
LISTVALUES_QUERY = "SELECT name FROM factoids WHERE value LIKE '%%%s%%'"

GET_D_RE = re.compile("^(?P<name>.+?)\??$")
GET_RE = re.compile("^(?P<name>.+?)\?$")
SET_RE = re.compile("^(?!no, +)(?P<name>.+?) +(is|are) +(?!also +)(?P<value>.+)$")
NO_RE = re.compile("^no, +(?P<name>.+?) +(is|are) +(?!also +)(?P<value>.+)$")
ALSO_RE = re.compile("^(?P<name>.+?) +(is|are) +also +(?P<value>.+)$")
DEL_RE = re.compile("^forget +(?P<name>.+)$")
REP_RE = re.compile("^(?P<name>.+?) +=~ +(?P<modstring>.+)$")
LOCK_RE = re.compile("^lock +(?P<name>.+)$")
UNLOCK_RE = re.compile("^unlock +(?P<name>.+)$")
INFO_RE = re.compile("^factinfo +(?P<name>.+)\??$")
STATUS_RE = re.compile("^status$")
LISTKEYS_RE = re.compile("^listkeys +(?P<name>.+)$")
LISTVALUES_RE = re.compile("^listvalues +(?P<name>.+)$")
TELL_RE = re.compile("^tell +(?P<nick>.+?) +about +(?P<name>.+)$")

REPLY_ACTION_RE = re.compile("^<(?P<type>reply|action)>\s*(?P<value>.+)$", re.I)
NULL_RE = re.compile("^<null>\s*$", re.I)

#----------------------------------------------------------------------------

MAX_FACT_NAME_LENGTH = 32
MAX_FACT_VAL_LENGTH = 455
MAX_FACT_SEARCH_RESULTS = 15

#----------------------------------------------------------------------------

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

#----------------------------------------------------------------------------

class SmartyPants(Plugin):
	"""
	This is the main infobot plugin, the factoid resolver.
	People say stupid shit, and this thing captures it for all time. Then
	they can later ask stupid questions, and we'll find their dumb answers
	for them.

	You can probably also get some random stats about the factoid database,
	too.
	"""
	
	#------------------------------------------------------------------------
	
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
	
	def __setup_config(self):
		self.__users = HangleUserList(self, 'InfobotUsers')
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
	
	def rehash(self):
		self.__setup_config()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		get_dir = PluginTextEvent(FACT_GET, IRCT_PUBLIC_D, GET_D_RE, priority=0)
		get_msg = PluginTextEvent(FACT_GET, IRCT_MSG, GET_D_RE, priority=0)
		get_pub = PluginTextEvent(FACT_GET, IRCT_PUBLIC, GET_RE, priority=0)
		set_dir = PluginTextEvent(FACT_SET, IRCT_PUBLIC_D, SET_RE, priority=1)
		set_msg = PluginTextEvent(FACT_SET, IRCT_MSG, SET_RE, priority=1)
		set_pub = PluginTextEvent(FACT_SET, IRCT_PUBLIC, SET_RE, priority=1)
		no_dir = PluginTextEvent(FACT_NO, IRCT_PUBLIC_D, NO_RE)
		no_msg = PluginTextEvent(FACT_NO, IRCT_MSG, NO_RE)
		also_dir = PluginTextEvent(FACT_ALSO, IRCT_PUBLIC_D, ALSO_RE)
		also_msg = PluginTextEvent(FACT_ALSO, IRCT_MSG, ALSO_RE)
		del_dir = PluginTextEvent(FACT_DEL, IRCT_PUBLIC_D, DEL_RE)
		del_msg = PluginTextEvent(FACT_DEL, IRCT_MSG, DEL_RE)
		rep_dir = PluginTextEvent(FACT_REPLACE, IRCT_PUBLIC_D, REP_RE)
		rep_msg = PluginTextEvent(FACT_REPLACE, IRCT_MSG, REP_RE)
		lock_dir = PluginTextEvent(FACT_LOCK, IRCT_PUBLIC_D, LOCK_RE)
		lock_msg = PluginTextEvent(FACT_LOCK, IRCT_MSG, LOCK_RE)
		unlock_dir = PluginTextEvent(FACT_UNLOCK, IRCT_PUBLIC_D, UNLOCK_RE)
		unlock_msg = PluginTextEvent(FACT_UNLOCK, IRCT_MSG, UNLOCK_RE)
		info_dir = PluginTextEvent(FACT_INFO, IRCT_PUBLIC_D, INFO_RE)
		info_msg = PluginTextEvent(FACT_INFO, IRCT_MSG, INFO_RE)
		status_dir = PluginTextEvent(FACT_STATUS, IRCT_PUBLIC_D, STATUS_RE)
		status_msg = PluginTextEvent(FACT_STATUS, IRCT_MSG, STATUS_RE)
		listkey_dir = PluginTextEvent(FACT_LISTKEYS, IRCT_PUBLIC_D, LISTKEYS_RE)
		listkey_msg = PluginTextEvent(FACT_LISTKEYS, IRCT_MSG, LISTKEYS_RE)
		listval_dir = PluginTextEvent(FACT_LISTVALUES, IRCT_PUBLIC_D, LISTVALUES_RE)
		listval_msg = PluginTextEvent(FACT_LISTVALUES, IRCT_MSG, LISTVALUES_RE)
		tell_dir = PluginTextEvent(FACT_TELL, IRCT_PUBLIC_D, TELL_RE)
		tell_msg = PluginTextEvent(FACT_TELL, IRCT_MSG, TELL_RE)
		
		self.register(get_dir, get_msg, set_dir, set_msg, no_dir, no_msg,
			also_dir, also_msg, del_dir, del_msg, rep_dir, rep_msg, lock_dir, lock_msg,
			unlock_dir, unlock_msg, info_dir, info_msg, status_dir, status_msg,
			listkey_dir, listkey_msg, listval_dir, listval_msg, tell_dir, tell_msg)
		if self.__get_pub:
			self.register(get_pub)
		if self.__set_pub:
			self.register(set_pub)

		self.__set_help_messages()
	
	#------------------------------------------------------------------------

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
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Check to see if this user is ignored
		#
		# This will possibly be superceeded if a blamehangle-wide ignore
		# list is implemented... but perhaps not. It could be useful to
		# only ignore a user here, but let them access other plugins. Maybe.
		if self.__users.check_user_flags(trigger.userinfo, 'ignore'):
			return
		
		# Someone wants to view a factoid.
		if trigger.name == FACT_GET:
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
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants to set a factoid. If the name is too long, tell them
		# to go to hell.
		elif trigger.name == FACT_SET:
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
			if re.search('=~', name):
				return
				
			if len(name) > MAX_FACT_NAME_LENGTH:
				if not trigger.event.IRCType == IRCT_PUBLIC:
					replytext = "factoid name is too long"
					self.sendReply(trigger, replytext)
			else:
				query = (GET_QUERY, name)
				self.dbQuery(trigger, query)
		
		# Somone just told us to replace the definition of a factoid with
		# a new one
		elif trigger.name == FACT_NO:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants to add to the definition of a factoid
		elif trigger.name == FACT_ALSO:
			name = self.__Sane_Name(trigger)
			if len(name) > MAX_FACT_NAME_LENGTH:
				replytext = "factoid name is too long"
				self.sendReply(trigger, replytext)
			else:
				query = (GET_QUERY, name)
				self.dbQuery(trigger, query)
		
		# Someone wants to delete a factoid
		elif trigger.name == FACT_DEL:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants to do a search/replace on a factoid
		elif trigger.name == FACT_REPLACE:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants to lock a factoid
		elif trigger.name == FACT_LOCK:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants to unlock a factoid
		elif trigger.name == FACT_UNLOCK:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone wants information on a factoid
		elif trigger.name == FACT_INFO:
			name = self.__Sane_Name(trigger)
			query = (INFO_QUERY, name)
			self.dbQuery(trigger, query)
		
		# Someone asked for our runtime status
		elif trigger.name == FACT_STATUS:
			query = (STATUS_QUERY, )
			self.dbQuery(trigger, query)
		
		# Someone asked to search by key
		elif trigger.name == FACT_LISTKEYS:
			name = self.__Sane_Name(trigger)
			name = name.replace("%", "\%")
			name = name.replace('"', '\\\"')
			name = name.replace("'", "\\\'")
			query =  (LISTKEYS_QUERY % name, )
			self.dbQuery(trigger, query)
		
		# Someone asked to search by value
		elif trigger.name == FACT_LISTVALUES:
			name = self.__Sane_Name(trigger)
			name = name.replace("%", "\%")
			name = name.replace('"', '\\\"')
			name = name.replace("'", "\\\'")
			query =  (LISTVALUES_QUERY % name, )
			self.dbQuery(trigger, query)
		
		# Someone wants us to tell someone else about a factoid
		elif trigger.name == FACT_TELL:
			name = self.__Sane_Name(trigger)
			query = (GET_QUERY, name)
			self.dbQuery(trigger, query)
	
	#------------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		trigger, results = message.data
		
		if trigger.name == FACT_GET:
			self.__Fact_Get(trigger, results)
		
		elif trigger.name == FACT_SET:
			self.__Fact_Set(trigger, results)
		
		elif trigger.name == FACT_NO:
			self.__Fact_No(trigger, results)
		
		elif trigger.name == FACT_ALSO:
			self.__Fact_Also(trigger, results)
		
		elif trigger.name == FACT_DEL:
			self.__Fact_Del(trigger, results)
		
		elif trigger.name == FACT_REPLACE:
			self.__Fact_Replace(trigger, results)
		
		elif trigger.name == FACT_LOCK:
			self.__Fact_Lock(trigger, results)
		
		elif trigger.name == FACT_UNLOCK:
			self.__Fact_Unlock(trigger, results)
		
		elif trigger.name == FACT_INFO:
			self.__Fact_Info(trigger, results)
			
		elif trigger.name == FACT_STATUS:
			self.__Fact_Status(trigger, results)
		
		elif trigger.name == FACT_LISTKEYS:
			self.__Fact_Search(trigger, results, "key")
		
		elif trigger.name == FACT_LISTVALUES:
			self.__Fact_Search(trigger, results, "value")
		
		elif trigger.name == FACT_TELL:
			self.__Fact_Tell(trigger, results)
		
		elif trigger.name == FACT_UPDATEDB:
			# The database just made our requested modifications, so we just
			# pass.
			pass
		
		else:
			# We got a wrong message, what the fuck?
			errtext = "Database sent SmartyPants an erroneous %s" % trigger
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	# Return a random item from stuff
	# -----------------------------------------------------------------------
	def __Random(self, stuff):
		a = random.randint(0, len(stuff)-1)
		return stuff[a]
	
	# -----------------------------------------------------------------------
	# A user asked to lookup a factoid. We've already dug it out of the
	# database, so all we need to do is formulate a reply and send it out.
	# -----------------------------------------------------------------------
	def __Fact_Get(self, trigger, results):
		replytext = ''
		
		if results == [()]:
			# The factoid wasn't in our database
			if trigger.event.IRCType == IRCT_PUBLIC:
				# Don't say anything if it was a public request
				return
			else:
				replytext = self.__Random(DUNNO)
				self.sendReply(trigger, replytext)
				
				self.__dunnos += 1
		
		else:
			# We found it!
			row = results[0][0]
			
			# <null> check
			m = NULL_RE.match(row['value'])
			if m:
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
			# TODO: return random dates to bug people?
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
				reply = PluginReply(trigger, replytext, process=0)
			else:
				replytext = '%(name)s is %(value)s' % row
				reply = PluginReply(trigger, replytext)
			
			self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
			
			# Update the request count and nick
			trigger.name = FACT_UPDATEDB
			
			name = row['name']
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			now = int(time.time())
			query = (REQUESTED_QUERY, requester_nick, requester_host, now, name)
			self.dbQuery(trigger, query)
	
	# -----------------------------------------------------------------------
	# A user just tried to set a factoid.. if it doesn't already exist, we
	# will go ahead and add it.
	# -----------------------------------------------------------------------
	def __Fact_Set(self, trigger, results):
		typ = type(results[0])
		
		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# The factoid wasn't in our database, so insert it
				#
				#INSERT INTO factoids (name, value, author_nick, author_host, created_time)
				name = self.__Sane_Name(trigger)
				value = trigger.match.group('value')
				if len(value) > MAX_FACT_VAL_LENGTH:
					replytext = "that's too long"
					self.sendReply(trigger, replytext)
				else:
					self.__sets += 1
					author_nick = trigger.userinfo.nick
					author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
					created_time = int(time.time())
					query = (SET_QUERY, name, value, author_nick, author_host, created_time)
					self.dbQuery(trigger, query)
			
			else:
				# It was already in our database

				# don't say anything if this was an undirected public
				if trigger.event.IRCType == IRCT_PUBLIC:
					return
				row = results[0][0]
				replytext = "...but '%(name)s' is already something else..." % row
				self.sendReply(trigger, replytext)
		
		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid insertion failed, warning, warning!'
			elif result == 1:
				if trigger.event.IRCType == IRCT_PUBLIC:
					# don't send a reply to an undirected public set
					return
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# A user just tried to update a factoid by replacing the existing
	# definition with a new one
	# -----------------------------------------------------------------------
	def __Fact_No(self, trigger, results):
		typ = type(results[0])
		name = self.__Sane_Name(trigger)
		value = trigger.match.group('value')
		
		if len(value) > MAX_FACT_VAL_LENGTH:
			replytext = "that's too long"
			self.sendReply(trigger, replytext)
			return
		
		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# this factoid wasn't in the db
				self.__sets += 1
				author_nick = trigger.userinfo.nick
				author_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
				created_time = int(time.time())
				query = (SET_QUERY, name, value, author_nick, author_host, created_time)
				self.dbQuery(trigger, query)
			
			else:
				# This factoid was in our db
				row = results[0][0]
				if row['locker_nick']:
					if not self.__users.check_user_flags(trigger.userinfo, 'lock'):
						replytext = "You don't have permission to alter locked factoids"
						self.sendReply(trigger, replytext)
						return
				if self.__users.check_user_flags(trigger.userinfo, 'delete'):
					# This user is okay
					self.__modifys += 1
					author_nick = trigger.userinfo.nick
					author_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
					created_time = int(time.time())
					del_q = (DEL_QUERY, name)
					set_q = (SET_QUERY, name, value, author_nick, author_host, created_time)
					self.dbQuery(trigger, del_q, set_q)
				else:
					# This user is not allowed to delete factoids, so
					# we won't let them overwrite either
					replytext = "You don't have permission to overwrite factoids"
					self.sendReply(trigger, replytext)

		# UPDATE reply
		elif typ == types.LongType:
			if len(results) == 2:
				result1, result2 = results
				if result1:
					if result2:
						replytext = self.__Random(OK)
					else:
						replytext = "factoid insertion failed, warning, warning!"
				else:
					replytext = "factoid deletion failed, warning, warning!"
			else:
				result = results[0]
				if result:
					replytext = self.__Random(OK)
				else:
					replytext = "factoid insertion failed, warning, warning!"
			
			self.sendReply(trigger, replytext)
			
	
	# -----------------------------------------------------------------------
	# A user just tried to update a factoid. If it exists, we add to its
	# definition, otherwise we make a new factoid.
	# -----------------------------------------------------------------------
	def __Fact_Also(self, trigger, results):
		typ = type(results[0])

		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# The factoid wasn't in our database, so insert it
				# We cheat a little here
				trigger.name = FACT_SET
				self.__Fact_Set(trigger, results)

			else:
				# It was already in our database, so add to the definition
				# if it fits, checking first to see if it is locked
				row = results[0][0]
				extra_value = trigger.match.group('value')
				if row['locker_nick']:
					if not self.__users.check_user_flags(trigger.userinfo, 'lock'):
						replytext = "you are not allowed to alter locked factoids"
						self.sendReply(trigger, replytext)
					
					else:
						new_value = "%s, or %s" % (row['value'], extra_value)
						self.__Fact_Update(trigger, new_value)
				else:
					new_value = "%s, or %s" % (row['value'], extra_value)
					self.__Fact_Update(trigger, new_value)
					
		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid insertion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)

	#------------------------------------------------------------------------
	# Update a factoid by adding our new text to the end of it
	#------------------------------------------------------------------------
	def __Fact_Update(self, trigger, value):
		self.__modifys += 1
		modified_time = int(time.time())
		modifier_nick = trigger.userinfo.nick
		modifier_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
		name = self.__Sane_Name(trigger)
		query = (MOD_QUERY, value, modifier_nick, modifier_host, modified_time, name)
		self.dbQuery(trigger, query)
	
	# -----------------------------------------------------------------------
	# Someone asked to delete a factoid.
	# Check their flags to see if they have permission, then delete or refuse
	# -----------------------------------------------------------------------
	def __Fact_Del(self, trigger, results):
		typ = type(results[0])
		
		# SELECT reply
		if typ == types.TupleType:
			name = self.__Sane_Name(trigger)
			
			if results == [()]:
				# The factoid wasn't in our database, tell whoever cares
				replytext = "no such factoid: '%s'" % name
				self.sendReply(trigger, replytext)
			
			else:
				# It was in our database, delete it!
				row = results[0][0]
				if row['locker_nick']:
					if not self.__users.check_user_flags(trigger.userinfo, 'lock'):
						replytext = "You don't have permission to alter locked factoids"
						self.sendReply(trigger, replytext)
						return
					else:
						replytext = "The factoid '%s' is locked, unlock it before deleting" % name
						self.sendReply(trigger, replytext)
						return

				if self.__users.check_user_flags(trigger.userinfo, 'delete'):
					self.__dels += 1
					query = (DEL_QUERY, name)
					self.dbQuery(trigger, query)
				else:
					replytext = "you don't have permission to delete factoids"
					self.sendReply(trigger, replytext)
		
		# DELETE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid deletion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	# A user just tried t odo a search/replace on a factoid.
	#------------------------------------------------------------------------
	def __Fact_Replace(self, trigger, results):
		typ = type(results[0])
		name = self.__Sane_Name(trigger)
		
		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# That factoid wasn't in our database
				replytext = "no such factoid: '\02%s\02'" % name
				self.sendReply(trigger, replytext)
			
			else:
				# It was in our database
				row = results[0][0]
				value = row['value']
				
				if row['locker_nick'] and not self.__users.check_user_flags(trigger.userinfo, 'lock'):
					replytext = "you don't have permission to alter locked factoids"
					self.sendReply(trigger, replytext)
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
							replytext = "that doesn't contain '%s'" % search
							self.sendReply(trigger, replytext)
							return
						
						# bitch at the user if they made the factoid too
						# long
						if len(new_value) > MAX_FACT_VAL_LENGTH:
							replytext = "that will make the factoid too long"
							self.sendReply(trigger, replytext)
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
					
					else:
						# we got a junk modstring
						replytext = "'%s' is not a valid search/replace string" % modstring
						self.sendReply(trigger, replytext)
				else:
					replytext = "'%s' is not a valid search/replace string" % modstring
					self.sendReply(trigger, replytext)
		
		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid insertion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)

	#------------------------------------------------------------------------
	# A user just tried to lock a factoid.
	# Check to make sure that they have the appropriate access, then
	# either lock the factoid or tell them to get lost
	#------------------------------------------------------------------------
	def __Fact_Lock(self, trigger, results):
		typ = type(results[0])
		name = self.__Sane_Name(trigger)
		
		# SELECT reply
		if typ == types.TupleType:
			if results == [()]:
				# The factoid wasn't in our database
				replytext = "no such factoid: '\02%s\02'" % name
				self.sendReply(trigger, replytext)
	
			else:
				# The factoid exists. Check if the user is allowed to
				# lock things.
				row = results[0][0]
				if self.__users.check_user_flags(trigger.userinfo, 'lock'):
					if row['locker_nick']:
						# this factoid is already locked
						replytext = "'\02%s\02' has already been locked by %s" % (name, row['locker_nick'])
						self.sendReply(trigger, replytext)
					else:
						# Not locked, so lock it
						locker_nick = trigger.userinfo.nick
						locker_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
						locked_time = int(time.time())
						query = (LOCK_QUERY, locker_nick, locker_host, locked_time, name)
						self.dbQuery(trigger, query)
				else:
					# this user is not allowed to lock factoids
					replytext = "you don't have permission to lock factoids"
					self.sendReply(trigger, replytext)

		# LOCK reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid deletion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)

	
	#------------------------------------------------------------------------
	# A user just tried to unlock a factoid.
	# Check to make sure that they have the appropriate access, then
	# either unlock the factoid or tell them to get lost
	#------------------------------------------------------------------------
	def __Fact_Unlock(self, trigger, results):
		typ = type(results[0])
		name = self.__Sane_Name(trigger)

		# SELECT reply
		if typ == types.TupleType:

			if results == [()]:
				# The factoid wasn't in our database
				replytext = "no such factoid: '\02%s\02'" % name
				self.sendReply(trigger, replytext)

			else:
				row = results[0][0]
				# The factoid exists. Check user permissions
				if self.__users.check_user_flags(trigger.userinfo, 'lock'):
					# check if the factoid is actually locked
					if row['locker_nick']:
						query =  (UNLOCK_QUERY, name)
						self.dbQuery(trigger, query)
					else:
						# this factoid wasn't locked
						replytext = "'\02%s\02' wasn't locked" % name
						self.sendReply(trigger, replytext)
				else:
					# this user is not allowed to unlock factoids
					replytext = "you don't have permission to unlock factoids"
					self.sendReply(trigger, replytext)
					
		# LOCK reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid deletion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
			self.sendReply(trigger, replytext)
			
	
	#------------------------------------------------------------------------
	# Someone asked for some info on a factoid.
	#------------------------------------------------------------------------
	def __Fact_Info(self, trigger, results):
		if results == [()]:
			# No such factoid
			replytext = 'there is no such factoid'
		
		else:
			row = results[0][0]
			
			now = int(time.time())
			then = row['created_time']
			row['created_time'] = self.__nice_time(now - then)
			text = '%(name)s -- created by %(author_nick)s (%(author_host)s), %(created_time)s ago'
			if row['request_count']:
				then = row['requested_time']
				row['requested_time'] = self.__nice_time(now - then)
				text += '; requested %(request_count)d time(s), last by %(requester_nick)s, %(requested_time)s ago'
			if row['modifier_nick']:
				then = row['modified_time']
				row['modified_time'] = self.__nice_time(now - then)
				text += '; last modified by %(modifier_nick)s (%(modifier_host)s), %(modified_time)s ago'
			if row['locker_nick']:
				then = row['locked_time']
				row['locked_time'] = self.__nice_time(now - then)
				text += '; locked by %(locker_nick)s (%(locker_host)s), %(locked_time)s ago'
			
			replytext = text % row
		
		self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	# Turn an amount of seconds into a nice string detailing how long it
	# is in english
	#------------------------------------------------------------------------
	def __nice_time(self, seconds):
		text = ""
		
		# a year
		if seconds >= 31536000:
			years = seconds / 31536000
			seconds %= 31536000
			text += "%d year" % years
			if years > 1:
				text += "s, "
			else:
				text += ", "
		
		# a day
		if seconds >= 86400:
			days = seconds / 86400
			seconds %= 86400
			text += "%d day" % days
			if days > 1:
				text += "s, "
			else:
				text += ", "
		
		# an hour
		if seconds >= 3600:
			hours = seconds / 3600
			seconds %= 3600
			text += "%d hour" % hours
			if hours > 1:
				text += "s, "
			else:
				text += ", "

		# a minute
		if seconds >= 60:
			minutes = seconds / 60
			seconds %= 60
			text += "%d minute" % minutes
			if minutes > 1:
				text += "s, "
			else:
				text += ", "
		
		# leftover seconds
		if seconds == 1:
			text += "%d second" % seconds
		else:
			text += "%d seconds" % seconds
		
		
		return text
	
	#------------------------------------------------------------------------
	# Someone just asked for our status
	#------------------------------------------------------------------------
	def __Fact_Status(self, trigger, results):
		row = results[0][0]
		num = row['total']
		replytext = "Since %s, there have been \02%d\02 requests, \02%d\02 modifications, \02%d\02 new factoids, \02%d\02 deletions, and \02%d\02 dunnos. I currently reference \02%d\02 factoids." % (self.__start_time, self.__requests, self.__modifys, self.__sets, self.__dels, self.__dunnos, num)
		self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	# Someone just asked to search the factoid database
	#------------------------------------------------------------------------
	def __Fact_Search(self, trigger, results, what):
		findme = self.__Sane_Name(trigger)
		if results == [()]:
			# the search failed
			replytext = "Factoid search of '\02%s\02' by %s returned no results." % (findme, what)
			self.sendReply(trigger, replytext)
		else:
			# check how many items we found
			results = results[0]
			if len(results) > MAX_FACT_SEARCH_RESULTS:
				replytext = "Factoid search of '\02%s\02' by %s yielded too many results. Please refine your query." % (findme, what)
				self.sendReply(trigger, replytext)
			else:
				# We found some items, but less than our max threshold, so
				# generate the reply
				replytext = "Factoid search of '\02%s\02' by %s (\02%d\02 results): " % (findme, what, len(results))
				while results:
					replytext += "%s" % results[0]['name']
					results = results[1:]
					if results:
							replytext += " \02;;\02 "
				
				self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	# Someone wants us to tell someone else about a factoid!
	#------------------------------------------------------------------------
	def __Fact_Tell(self, trigger, results):
		typ = type(results[0])

		# SELECT reply
		if typ == types.TupleType:
			name = self.__Sane_Name(trigger)
			tellnick = trigger.match.group('nick')
		
			if results == [()]:
				# The factoid didn't exist
				self.__dunnos += 1
				replytext = "no such factoid, '\02%s\02'" % name
				self.sendReply(trigger, replytext)

			else:
				self.__requests += 1
				row = results[0][0]
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
				query = (REQUESTED_QUERY, requester_nick, requester_host, now, name)
				self.dbQuery(trigger, query)

		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid stats update failed, warning, warning!'
				self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Return a sanitised factoid name.
	def __Sane_Name(self, trigger):
		# lower case
		newname = trigger.match.group('name').lower()
		# translate the name according to our table
		newname = newname.translate(self.__trans)
		# remove any bad chars now
		newname = newname.replace('\x00', '')
		
		return newname
