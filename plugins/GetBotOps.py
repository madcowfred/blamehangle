# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004, MadCowDisease
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

'Asks configured eggdrop bots for ops.'

import random
import re

from classes.Common import CompileMask
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class GetBotOps(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('GetBotOps', autosplit=True)
		
		self.__Bots = {}
		for network, chans in self.Options['channels'].items():
			self.__Bots[network] = {}
			for chan in chans:
				chanopts = self.OptionsDict('GetBotOps.%s.%s' % (network, chan))
				
				self.__Bots[network][chan] = {
					'bots': [],
					'pass': chanopts['password'],
				}
				
				# Keep a compiled version of the mask around
				for mask in chanopts['bot'].values():
					self.__Bots[network][chan]['bots'].append(CompileMask(mask))
				
				# Randomly shuffle the bot list so we don't always try the same
				# bot first.
				random.shuffle(self.__Bots[network][chan]['bots'])
	
	def register(self):
		if self.Options['channels']:
			self.addTimedEvent(
				method = self.__GetBotOps,
				interval = self.Options['request_interval'],
				targets = self.Options['channels'],
			)
	
	# -----------------------------------------------------------------------
	
	def __GetBotOps(self, trigger):
		# We need wrap objects
		self.sendMessage('ChatterGizmo', REQ_WRAPS, self.Options['channels'].keys())
	
	def _message_REPLY_WRAPS(self, message):
		for net, wrap in message.data.items():
			if not wrap.connected():
				continue
			
			ournick = wrap.conn.getnick()
			
			for chan, data in self.__Bots[net].items():
				# We need to wait for the channel to be synched
				if chan not in wrap.ircul._c or not wrap.ircul._c[chan].synched:
					continue
				
				# If we're already opped, there's no point asking
				if wrap.ircul.user_has_mode(chan, ournick, 'o'):
					continue
				
				# See if we have any matching bots
				for regexp in data['bots']:
					matches = wrap.ircul.user_matches(chan, regexp)
					found = 0
					for ui in matches:
						# If he's opped, ask him for ops
						if wrap.ircul.user_has_mode(chan, ui.nick, 'o'):
							text = 'OP %s %s' % (data['pass'], chan)
							self.privmsg(wrap, ui.nick, text)
							
							tolog = 'Asked %s for ops on %s.' % (ui.nick, chan)
							self.connlog(wrap, LOG_ALWAYS, tolog)
							
							found = 1
							break
					
					# If we found one, rearrange the bot list a bit so we try
					# a different bot next time.
					if found:
						data['bots'] = data['bots'][1:] + data['bots'][:1]
						break

# ---------------------------------------------------------------------------
