#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains (or at least will contain!) the factoid resolver.
#
# It was too much pain to have this split into a seperate table for the
# locks for too little reward. I merged it back in.
#
# The factoid resolver uses the following SQL table:
# CREATE TABLE factoids (
# 	name varchar(64) NOT NULL default '',
#	value text NOT NULL,
#	author_nick varchar(64) default NULL,
#	author_host varchar(192) default NULL,
#	modifier_nick varchar(64) default NULL,
#	modifier_host varchar(192) default NULL,
#	requester_nick varchar(64) default NULL,
#	requester_host varchar(192) default NULL,
#	request_count int(11) NOT NULL default 0,
#	locker_nick varchar(64) default NULL,
#	locker_host varchar(192) default NULL,
#	created_time int(11) default NULL,
#	modified_time int(11) default NULL,
#	requested_time int(11) default NULL,
#	locked_time varchar (11) default NULL,
#	PRIMARY KEY (name)
# ) TYPE=MyISAM;
#

import random
import re
import time
import types

from classes.Plugin import *
from classes.Constants import *

#----------------------------------------------------------------------------

FACT_SET = "FACT_SET"
FACT_GET = "FACT_GET"
FACT_ALSO = "FACT_ALSO"
FACT_DEL = "FACT_DEL"
FACT_REPLACE = "FACT_REPLACE"
FACT_INFO = "FACT_INFO"
#FACT_STATUS = "FACT_STATUS"
FACT_LOCK = "FACT_LOCK"
FACT_UNLOCK = "FACT_UNLOCK"

FACT_UPDATEDB = "FACT_MOD"

GET_QUERY = "SELECT name, value, locker_nick FROM factoids WHERE name = %s"
SET_QUERY = "INSERT INTO factoids (name, value, author_nick, author_host, created_time) VALUES (%s, %s, %s, %s, %s)"
MOD_QUERY = "UPDATE factoids SET value = %s, modifier_nick = %s, modifier_host = %s, modified_time = %s WHERE name = %s"
DEL_QUERY = "DELETE FROM factoids WHERE name = %s"
INFO_QUERY = "SELECT * FROM factoids WHERE name = %s"

REQUESTED_QUERY = "UPDATE factoids SET request_count = request_count + 1, requester_nick = %s, requester_host = %s WHERE name = %s"

LOCK_QUERY = "UPDATE factoids SET locker_nick = %s, locker_host = %s, locked_time = %s WHERE name = %s"
UNLOCK_QUERY = "UPDATE factoids SET locker_nick = NULL, locker_host = NULL, locked_time = NULL WHERE name = %s"

GET_RE = re.compile("^(?P<name>.+?)\??$")
SET_RE = re.compile("^(?P<name>.+?) (is|are) (?!also )(?P<value>.+)$")
ALSO_RE = re.compile("(?P<name>.+?) (is|are) also (?P<value>.+)$")
DEL_RE = re.compile("^forget (?P<name>.+)$")
REP_RE = re.compile("^(?P<name>.+?) =~ (?P<modstring>.+)$")
LOCK_RE = re.compile("^lock (?P<name>.+)$")
UNLOCK_RE = re.compile("^unlock (?P<name>.+)$")
INFO_RE = re.compile("^factinfo (?P<name>.+)\??$")
#STATUS_RE = re.compile("^status$")

MAX_FACT_NAME_LENGTH = 32
MAX_FACT_VAL_LENGTH = 455

#----------------------------------------------------------------------------

OK = [
	"OK",
	"you got it",
	"done"
]

DUNNO = [
	"no idea",
	"I don't know",
	"you got me",
	"not a clue"
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
		self.__users = FactoidUserList()
		self.__Setup_Users()

	def _message_PLUGIN_REGISTER(self, message):
		get_dir = PluginTextEvent(FACT_GET, IRCT_PUBLIC_D, GET_RE, exclusive=1)
		get_msg = PluginTextEvent(FACT_GET, IRCT_MSG, GET_RE, exclusive=1)
		set_dir = PluginTextEvent(FACT_SET, IRCT_PUBLIC_D, SET_RE)
		set_msg = PluginTextEvent(FACT_SET, IRCT_MSG, SET_RE)
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
		
		self.register(get_dir, get_msg, set_dir, set_msg, also_dir, also_msg, del_dir, del_msg, rep_dir, rep_msg, lock_dir, lock_msg, unlock_dir, unlock_msg, info_dir, info_msg)
	
	#------------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone wants to view a factoid.
		if trigger.name == FACT_GET:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		# Someone wants to set a factoid. If the name is too long, tell them
		# to go to hell.
		elif trigger.name == FACT_SET:
			name = trigger.match.group('name')
			if len(name) > MAX_FACT_NAME_LENGTH:
				replytext = "factoid name is too long"
				self.sendReply(trigger, replytext)
			else:
				data = [trigger, (GET_QUERY, [name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)

		# Someone wants to add to the definition of a factoid
		elif trigger.name == FACT_ALSO:
			name = trigger.match.group('name')
			if len(name) > MAX_FACT_NAME_LENGTH:
				replytext = "factoid name is too long"
				self.sendReply(trigger, replytext)
			else:
				data = [trigger, (GET_QUERY, [name])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		# Someone wants to delete a factoid
		elif trigger.name == FACT_DEL:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)

		# Someone wants to do a search/replace on a factoid
		elif trigger.name == FACT_REPLACE:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)

		# Someone wants to lock a factoid
		elif trigger.name == FACT_LOCK:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)

		# Someone wants to unlock a factoid
		elif trigger.name == FACT_UNLOCK:
			name = trigger.match.group('name')
			data = [trigger, (GET_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		# Someone wants information on a factoid
		elif trigger.name == FACT_INFO:
			name = trigger.match.group('name')
			data = [trigger, (INFO_QUERY, [name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	#------------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		trigger, results = message.data
		
		if trigger.name == FACT_GET:
			self.__Fact_Get(trigger, results)
		
		elif trigger.name == FACT_SET:
			self.__Fact_Set(trigger, results)

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
		if results == [()]:
			# The factoid wasn't in our database
			replytext = self.__Random(DUNNO)
		
		else:
			# We found it!
			row = results[0][0]
			replytext = '%(name)s is %(value)s' % row
			
			# Update the request count and nick
			trigger.name = FACT_UPDATEDB
			
			name = row['name']
			requester_nick = trigger.userinfo.nick
			requester_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
			data = [trigger, (REQUESTED_QUERY, [requester_nick, requester_host, name])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)
		
		self.sendReply(trigger, replytext)
	
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
				
				name = trigger.match.group('name')
				value = trigger.match.group('value')
				author_nick = trigger.userinfo.nick
				author_host = '%s@%s' % (trigger.userinfo.ident, trigger.userinfo.host)
				created_time = time.time()
				data = [trigger, (SET_QUERY, [name, value, author_nick, author_host, created_time])]
				
				self.sendMessage('DataMonkey', REQ_QUERY, data)
			
			else:
				# It was already in our database
				row = results[0][0]
				replytext = "...but '%(name)s' is already something else..." % row
				self.sendReply(trigger, replytext)
		
		# UPDATE reply
		elif typ == types.LongType:
			result = results[0]
			if result == 0:
				replytext = 'factoid insertion failed, warning, warning!'
			elif result == 1:
				replytext = self.__Random(OK)
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
					if not self.__Check_User_Flags(trigger.userinfo, 'lock'):
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
		modified_time = time.time()
		modifier_nick = trigger.userinfo.nick
		modifier_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
		name = trigger.match.group('name')
		data = [trigger, (MOD_QUERY, [value, modifier_nick, modifier_host, modified_time, name])]
		self.sendMessage('DataMonkey', REQ_QUERY, data)
							
					

	# -----------------------------------------------------------------------
	# Someone asked to delete a factoid.
	#
	# This should be expanded to include user permission stuff, so not just
	# anyone can delete factoids.
	# -----------------------------------------------------------------------
	def __Fact_Del(self, trigger, results):
		typ = type(results[0])
		
		# SELECT reply
		if typ == types.TupleType:
			name = trigger.match.group('name')
			
			if results == [()]:
				# The factoid wasn't in our database, tell whoever cares
				replytext = "no such factoid: '%s'" % name
				self.sendReply(trigger, replytext)
			
			else:
				# It was in our database, delete it!
				if self.__Check_User_Flags(trigger.userinfo, 'delete'):
					data = [trigger, (DEL_QUERY, [name])]
					self.sendMessage('DataMonkey', REQ_QUERY, data)
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
		name = trigger.match.group('name')

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

				if row['locker_nick'] and not self.__Check_User_Flags(trigger.userinfo, 'lock'):
					replytext = "you don't have permission to alter locked factoids"
					self.sendReply(trigger, replytext)
					return
				
				modstring = trigger.match.group('modstring')
				if modstring.startswith("s"):
					bits = modstring.split(modstring[1])
					# break the modstring into its components
					if len(bits) == 4:
						search = bits[1]
						replace = bits[2]
						try:
							s = re.compile(search)
						except:
							replytext = "'%s is not a valid regexp" % search
							self.sendReply(trigger, replytext)
						else:
							new_value = re.sub(s, replace, value)
							if len(new_value) > MAX_FACT_VAL_LENGTH:
								replytext = "that will make the factoid too long"
								self.sendReply(trigger, replytext)
							else:
								# make the changes!
								self.__Fact_Update(trigger, new_value)
								
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
		name = trigger.match.group('name')
		
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
				if self.__Check_User_Flags(trigger.userinfo, 'lock'):
					if row['locker_nick']:
						# this factoid is already locked
						replytext = "'\02%s\02' has already been locked by %s" % (name, row['locker_nick'])
						self.sendReply(trigger, replytext)
					else:
						# Not locked, so lock it
						locker_nick = trigger.userinfo.nick
						locker_host = "%s@%s" % (trigger.userinfo.ident, trigger.userinfo.host)
						locked_time = time.time()
						data = [trigger, (LOCK_QUERY, [locker_nick, locker_host, locked_time, name])]
						self.sendMessage('DataMonkey', REQ_QUERY, data)
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
		name = trigger.match.group('name')

		# SELECT reply
		if typ == types.TupleType:

			if results == [()]:
				# The factoid wasn't in our database
				replytext = "no such factoid: '\02%s\02'" % name
				self.sendReply(trigger, replytext)

			else:
				row = results[0][0]
				# The factoid exists. Check user permissions
				if self.__Check_User_Flags(trigger.userinfo, 'lock'):
					# check if the factoid is actually locked
					if row['locker_nick']:
						data = [trigger, (UNLOCK_QUERY, [name])]
						self.sendMessage('DataMonkey', REQ_QUERY, data)
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
			
			now = time.time()
			
			text = '%(name)s -- created by %(author_nick)s (%(author_host)s), some time ago'
			if row['request_count']:
				#diff = row['requested_time'] - time.time()
				text += '; requested %(request_count)d time(s), last by %(requester_nick)s, some time ago'
			if row['modifier_nick']:
				text += '; last modified by %(modifier_nick)s (%(modifier_host)s), some time ago'
			
			replytext = text % row
		
		self.sendReply(trigger, replytext)
	
	#------------------------------------------------------------------------
	
	# The DB has performed our requested update to the factoid table
	#def __fact_update(self, text, result, conn, IRCtype, target, userinfo):
	#	replytext = self.__random_donetext()
	#	reply = [replytext, conn, IRCtype, target, userinfo]
	#	self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------
	
	# Check if the supplied irc user has access to delete factoids from our
	# database
	def __Check_User_Flags(self, userinfo, flag):
		matches = self.__users.host_match(userinfo.hostmask)
		if matches:
			for user in matches:
				if flag in user.flags:
					return 1

		return 0

	# -----------------------------------------------------------------------
	
	# Config mangling to grab our list of users.
	def __Setup_Users(self):
		try:
			options = self.Config.options('InfobotUsers')
		except:
			tolog = "no InfobotUsers section found!"
			self.putlog(LOG_WARNING, tolog)
		else:
			for option in options:
				try:
					[nick, part] = option.split('.')
				except:
					tolog = "malformed user option in factoid config: %s" % option
					self.putlog(LOG_WARNING, tolog)
				else:
					if part == 'hostmasks':
						hostmasks = self.Config.get('InfobotUsers', option).lower().split()
						flags = self.Config.get('InfobotUsers', nick + ".flags").lower().split()
						nick = nick.lower()
	
						user = FactoidUser(nick, hostmasks, flags)
						
						tolog = "SmartyPants: user %s" % user
						self.putlog(LOG_DEBUG, tolog)
	
						self.__users.add_user(user)
						
# ---------------------------------------------------------------------------

# This class wraps up everything we need to know about a user's permissions
# regarding the SmartyPants
class FactoidUser:
	def __init__(self, nick, hostmasks, flags):
		self.nick = nick
		self.flags = flags
		self.hostmasks = []
		self.regexps = []
		
		for hostmask in hostmasks:
			mask = "^%s$" % hostmask
			mask = mask.replace('.', '\\.')
			mask = mask.replace('?', '.')
			mask = mask.replace('*', '.*?')
			
			self.hostmasks.append(mask)
			self.regexps.append(re.compile(mask))
	
	def __str__(self):
		text = "%s %s %s" % (self.nick, self.hostmasks, self.flags)
		return text
	
	def __repr__(self):
		text = "<class FactoidUser:" + self.__str__() + ">"
		return text

# ---------------------------------------------------------------------------

# The userlist for SmartyPants.
class FactoidUserList:
	def __init__(self):
		self.__users = {}
	
	def __getitem__(self, item):
		return self.__users[item]
	
	def __delitem__(self, item):
		del self.__users[item]
	
	def add_user(self, user):
		self.__users[user.nick] = user
	
	# Check if the supplied hostname matches any of the hostmasks supplied
	# for users in the userlist. Return any users that matched.
	def host_match(self, hostname):
		matches = []
		for user in self.__users:
			for regexp in self.__users[user].regexps:
				if regexp.match(hostname):
					if self.__users[user] not in matches:
						matches.append(self.__users[user])
		
		
		return matches
