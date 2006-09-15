# ---------------------------------------------------------------------------
# $Id: GetBotOps.py 3795 2005-07-31 12:41:24Z freddie $
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2006, blamehangle team
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

'Does something quite undistinguishable from magic.'

import random
import re
from sre_constants import error as CompileError

from classes.Constants import *
from classes.Plugin import Plugin, PluginFakeTrigger

# ---------------------------------------------------------------------------

SELECT_QUERY = 'SELECT * FROM goonhooks'
INSERT_QUERY = 'INSERT INTO goonhooks (hook, reply) VALUES (%s, %s)'
DELETE_QUERY = 'DELETE FROM goonhooks WHERE hook = %s'

# Characters we need to escape
ESCAPE_RE = re.compile(r'([\+\[\]\(\)\|])')
# Match a regexp hook: /ababab/
REGEXP_RE = re.compile(r'^/(.*)/$')
# Match a nested hook: {blah}
NESTED_RE = re.compile(r'(\{[^\}]+\})')
# Match a split group: (blah|foo|meow)
SPLIT_RE = re.compile(r'(\([^\)]+\|[^\)]+\))')

# ---------------------------------------------------------------------------

class GoonHooks(Plugin):
	_UsesDatabase = 'GoonHooks'
	
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__Query_GetHooks()
	
	def register(self):
		# Add a hook
		self.addTextEvent(
			method = self.__Query_AddHook,
			regexp = r'^addhook (?P<hook>.*?) => (?P<reply>.+)$',
		)
		# Delete a hook
		self.addTextEvent(
			method = self.__Query_DelHook,
			regexp = r'^delhook (?P<hook>.+)$',
		)
		
		# Low priority event for matching
		self.addTextEvent(
			method = self.__Match_Hook,
			regexp = r'^(.+)$',
			priority = -10,
			IRCTypes = (IRCT_PUBLIC, IRCT_ACTION),
		)
	
	# -----------------------------------------------------------------------
	# Get our hooks from the database
	def __Query_GetHooks(self):
		self.__Hooks = {}
		trigger = PluginFakeTrigger('GOONHOOKS_GET')
		self.dbQuery(trigger, self.__Reply_GetHooks, SELECT_QUERY)
	
	# Compile any returned hooks into regexps
	def __Reply_GetHooks(self, trigger, result):
		# Error
		if result is None:
			return
		
		# No result
		elif result == ():
			return
		
		else:
			# {hook, reply}
			for row in result:
				matchme = self.__Compile_Hook(row['hook'])
				if matchme is None:
					tolog = 'Hook compilation failed: %r' % (row['hook'])
					self.putlog(LOG_WARNING, tolog)
				else:
					self.__Hooks[row['hook']] = (matchme, row['reply'])
	
	# Turn a hook string into a compiled regexp object
	def __Compile_Hook(self, hook):
		m = REGEXP_RE.match(hook)
		# Regular expression
		if m:
			r = m.group(1)
		else:
			# Fix up wildcard matches
			r = hook.replace('*', '.*')
			r = r.replace('?', '.')
			# Escape some icky regexp chars
			r = ESCAPE_RE.sub(r'\\\1', r)
			# Always match the whole string
			r = '^%s$' % (r)
		
		try:
			matchme = re.compile(r)
		except CompileError:
			return None
		else:
			return matchme
	
	# -----------------------------------------------------------------------
	# See if what someone just said matches any of our hooks
	def __Match_Hook(self, trigger):
		text = trigger.match.group(1)
		
		for hook, (matchme, reply) in self.__Hooks.items():
			matchobj = matchme.search(text)
			if matchobj is None:
				continue
			
			# Do regexp replaces first?
			groups = matchobj.groups()
			if len(groups) > 0:
				for i in range(len(groups)):
					reply = reply.replace('<%s>' % (i+1), groups[i])
			
			# Resolve any nestings
			nested = 0
			m = NESTED_RE.search(reply)
			while m is not None:
				nested += 1
				if nested > 100:
					break
				
				nesthook = m.group(1)[1:-1]
				if nesthook in self.__Hooks:
					nestreply = self.__Hooks[nesthook][1]
				else:
					nestreply = '??%s??' % (nesthook)
				reply = '%s%s%s' % (reply[:m.start(1)], nestreply, reply[m.end(1):])
				
				m = NESTED_RE.search(reply)
			
			# Pick a random reply for expansions
			m = SPLIT_RE.search(reply)
			while m is not None:
				choices = m.group(1)[1:-1].split('|')
				choice = random.choice(choices)
				reply = '%s%s%s' % (reply[:m.start(1)], choice, reply[m.end(1):])
				
				m = SPLIT_RE.search(reply)
			
			# Replace channels/nicknames in the output
			reply = reply.replace('<chan>', trigger.target.lower())
			reply = reply.replace('<nick>', trigger.userinfo.nick)
			
			# It might be an action
			if reply.startswith('<me> '):
				reply = '\x01ACTION %s\x01' % (reply[5:])
			
			# Send the reply if there is one
			if reply:
				self.sendReply(trigger, reply, process=0)
			
			break
	
	# -----------------------------------------------------------------------
	# Add a new hook if it doesn't exist
	def __Query_AddHook(self, trigger):
		hook = trigger.match.group('hook').lower()
		reply = trigger.match.group('reply')
		
		if hook in self.__Hooks:
			self.sendReply(trigger, 'Hook already exists!')
		else:
			matchme = self.__Compile_Hook(hook)
			if matchme is None:
				tolog = 'Hook compilation failed: %r' % (hook)
				self.putlog(LOG_WARNING, tolog)
				self.sendReply(trigger, 'Hook compilation failed.')
			else:
				self.dbQuery(trigger, self.__Reply_AddHook, INSERT_QUERY, hook, reply)
	
	def __Reply_AddHook(self, trigger, result):
		# Error
		if result is None:
			self.sendReply(trigger, 'Database error!')
			return
		
		# Insert failed somehow
		elif result == 0:
			self.sendReply(trigger, 'INSERT failed!')
			return
		
		# Inserted
		else:
			hook = trigger.match.group('hook').lower()
			reply = trigger.match.group('reply')
			
			matchme = self.__Compile_Hook(hook)
			self.__Hooks[hook] = (matchme, reply)
			
			self.sendReply(trigger, 'done.')
	
	# -----------------------------------------------------------------------
	# Delete a hook
	def __Query_DelHook(self, trigger):
		hook = trigger.match.group('hook').lower()
		
		if hook in self.__Hooks:
			self.dbQuery(trigger, self.__Reply_DelHook, DELETE_QUERY, hook)
		else:
			self.sendReply(trigger, "Hook doesn't exist!")
	
	def __Reply_DelHook(self, trigger, result):
		# Error
		if result is None:
			self.sendReply(trigger, 'Database error!')
			return
		
		# Delete failed somehow
		elif result == 0:
			self.sendReply(trigger, 'DELETE failed!')
			return
		
		# Deleted
		else:
			hook = trigger.match.group('hook')
			if hook in self.__Hooks:
				del self.__Hooks[hook]
			
			self.sendReply(trigger, 'done.')

# ---------------------------------------------------------------------------
