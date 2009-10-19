# Copyright (c) 2003-2009, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
This file contains the classes describing userlists for blamehangle, and
classes for representing the users themselves in the userlist.
"""

import re

from classes.Common import CompileMask
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
			
			# If we didn't, something is wrong
			#else:
			#	tolog = "Didn't find hostmasks and flags entries for '%s'!" % (nick)
	
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
			self.hostmasks.append(hostmask)
			self.regexps.append(CompileMask(hostmask))
	
	def __str__(self):
		text = "%s %s %s" % (self.nick, self.hostmasks, self.flags)
		return text
	
	def __repr__(self):
		text = "<class HangleUser:" + self.__str__() + ">"
		return text
	
	def Has_Flag(self, plugin, flag):
		return self.flags.get(plugin.lower(), {}).get(flag, None) != None

# ---------------------------------------------------------------------------
