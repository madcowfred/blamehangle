# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# A collection of silly games for people to play.

import random
import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

GAMES_EIGHTBALL = 'GAMES_EIGHTBALL'
EIGHTBALL_RE = re.compile('^8ball (?P<question>.+)$')
EIGHTBALL_HELP = '\028ball\02 <question> : The magic 8 ball will answer your question!'

# ---------------------------------------------------------------------------

class Games(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		eightball_dir = PluginTextEvent(GAMES_EIGHTBALL, IRCT_PUBLIC_D, EIGHTBALL_RE)
		eightball_msg = PluginTextEvent(GAMES_EIGHTBALL, IRCT_MSG, EIGHTBALL_RE)
		self.register(eightball_dir, eightball_msg)
		
		self.setHelp('games', '8ball', EIGHTBALL_HELP)
		
		self.registerHelp()
		
		self.__eightball_last = ''
		# Load the 8ball responses
		self.__eightball_responses = []
		for option in self.Config.options('eightball'):
			if option.startswith('response'):
				self.__eightball_responses.append(self.Config.get('eightball', option))
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == GAMES_EIGHTBALL:
			self.__Eightball(trigger)
	
	# -----------------------------------------------------------------------
	
	def __Eightball(self, trigger):
		while 1:
			replytext = random.choice(self.__eightball_responses)
			if replytext != self.__eightball_last:
				self.__eightball_last = replytext
				break
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
