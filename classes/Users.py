# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the classes describing userlists for blamehangle, and
# classes for representing the users themselves in the userlist

import re
from classes.Constants import *

# The userlist
class HangleUserList:
	def __init__(self, parent, ini_section):
		self.__users = {}
		self.__setup_users(parent, ini_section)
	
	def __getitem__(self, item):
		return self.__users[item]
	
	def __delitem__(self, item):
		del self.__users[item]
	
	#def add_user(self, user):
		#self.__users[user.nick] = user
	
	# -----------------------------------------------------------------------
	
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
	
	# -----------------------------------------------------------------------
	
	# Check if the supplied irc user has access to delete factoids from our
	# database
	def check_user_flags(self, userinfo, flag):
		matches = self.host_match(userinfo.hostmask)
		if matches:
			for user in matches:
				if flag in user.flags:
					return 1
		return 0

	# -----------------------------------------------------------------------
	
	# Config mangling to grab our list of users.
	def __setup_users(self, parent, ini_section):
		try:
			options = parent.Config.options(ini_section)
		except:
			tolog = "no %s section found!" % ini_section
			parent.putlog(LOG_WARNING, tolog)
		else:
			for option in options:
				try:
					[nick, part] = option.split('.')
				except:
					tolog = "malformed user option in factoid config: %s" % option
					parent.putlog(LOG_WARNING, tolog)
				else:
					if part == 'hostmasks':
						hostmasks = parent.Config.get(ini_section, option).lower().split()
						flags = parent.Config.get(ini_section, nick + ".flags").lower().split()
						nick = nick.lower()
	
						user = HangleUser(nick, hostmasks, flags)
						
						tolog = "<%s>: %s" % (ini_section, user)
						parent.putlog(LOG_DEBUG, tolog)
	
						self.__users[user.nick] = user

						
# ---------------------------------------------------------------------------

# This class wraps up everything we need to know about a user's permissions
class HangleUser:
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
			
			self.hostmasks.append(hostmask)
			self.regexps.append(re.compile(mask))
	
	def __str__(self):
		text = "%s %s %s" % (self.nick, self.hostmasks, self.flags)
		return text
	
	def __repr__(self):
		text = "<class HangleUser:" + self.__str__() + ">"
		return text

# ---------------------------------------------------------------------------

