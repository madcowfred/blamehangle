# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Asks configured eggdrop bots for ops.'

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
				
				for mask in chanopts['bot'].values():
					self.__Bots[network][chan]['bots'].append(CompileMask(mask))
	
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
				
				# If we're not in the userlist yet, we have to wait
				if wrap.ircul.user_has_mode(chan, ournick, 'o'):
					continue
				
				# See if we have any matching bots
				for regexp in data['bots']:
					matches = wrap.ircul.user_matches(chan, regexp)
					found = 0
					for ui in matches:
						# If he's opped, ask him for ops
						if wrap.ircul.user_has_mode(chan, ui.nick, 'o'):
							self.privmsg(wrap, ui.nick, 'OP %s' % data['pass'])
							
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
