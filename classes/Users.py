# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the classes describing userlists for blamehangle, and
# classes for representing the users themselves in the userlist

import re

from classes.Constants import *

# ---------------------------------------------------------------------------
# The userlist
class HangleUserList:
	def __init__(self, parent):
		self.parent = parent
		self.Config = parent.Config
		
		self.__users = {}
	
	# Load (or reload) the userlist
	def Reload(self):
		# Clean out old entries
		for key in self.__users.keys():
			del self.__users[key]
		
		# Add the users
		for section in self.Config.sections():
			if not section.startswith('User.'):
				continue
			
			flags = {}
			masks = []
			
			junk, nick = section.split('.', 1)
			
			# Sort out the options
			for option in self.Config.options(section):
				if option == 'hostmasks':
					masks = self.Config.get(section, option).split()
				
				elif option.startswith('flags.'):
					junk, plugin = option.split('.', 1)
					flags[plugin] = {}
					for flag in self.Config.get(section, option).lower().split():
						flags[plugin][flag] = 1
			
			# If we found flags and masks, this user is usable
			if flags and masks:
				user = HangleUser(nick, masks, flags)
				self.__users[nick] = user
				
				#self.parent.putlog(LOG_DEBUG, user)
			
			# If we didn't, something is wrong
			else:
				tolog = "Didn't find hostmasks and flags entries for '%s'!" % (nick)
				#self.parent.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Check if the supplied hostname matches any of the hostmasks supplied
	# for users in the userlist. Return any users that matched.
	def __Match_Host(self, hostmask):
		matches = []
		for name, user in self.__users.items():
			for regexp in user.regexps:
				if regexp.match(hostmask):
					matches.append(user)
					break
		return matches
	
	# -----------------------------------------------------------------------
	# Check if the supplied irc user has the required flag
	def Has_Flag(self, userinfo, plugin, flag):
		matches = self.__Match_Host(userinfo.hostmask())
		for user in matches:
			if user.Has_Flag(plugin, flag):
				return 1
		return 0

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
			self.regexps.append(re.compile(mask, re.I))
	
	def __str__(self):
		text = "%s %s %s" % (self.nick, self.hostmasks, self.flags)
		return text
	
	def __repr__(self):
		text = "<class HangleUser:" + self.__str__() + ">"
		return text
	
	def Has_Flag(self, plugin, flag):
		return self.flags.get(plugin.lower(), {}).get(flag, None) != None

# ---------------------------------------------------------------------------
