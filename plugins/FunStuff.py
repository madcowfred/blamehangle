# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# A collection of silly things for people to play with.

import random
import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

FUN_EIGHTBALL = 'FUN_EIGHTBALL'
EIGHTBALL_RE = re.compile('^8ball (?P<question>.+)$')
EIGHTBALL_HELP = '\028ball\02 <question> : The magic 8 ball will answer your question!'

FUN_MUDDLE = 'FUN_MUDDLE'
MUDDLE_RE = re.compile('^muddle (?P<text>.+)$')
MUDDLE_HELP = '\02muddle\02 <text> : Muddles your text by rearranging words.'

# ---------------------------------------------------------------------------

class FunStuff(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__eightball_last = ''
		# Load the 8ball responses
		self.__eightball_responses = []
		for option in self.Config.options('eightball'):
			if option.startswith('response'):
				self.__eightball_responses.append(self.Config.get('eightball', option))
	
	def _message_PLUGIN_REGISTER(self, message):
		self.setTextEvent(FUN_EIGHTBALL, EIGHTBALL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_MUDDLE, MUDDLE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('funstuff', '8ball', EIGHTBALL_HELP)
		self.setHelp('funstuff', 'muddle', MUDDLE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Come up with a random response to a question
	def _trigger_FUN_EIGHTBALL(self, trigger):
		while 1:
			replytext = random.choice(self.__eightball_responses)
			if replytext != self.__eightball_last:
				self.__eightball_last = replytext
				break
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Muddle up some text by re-arranging the words
	def _trigger_FUN_MUDDLE(self, trigger):
		words = trigger.match.group('text').split()
		new = []
		
		while words:
			# Pick a random word to pop
			i = random.randint(0, len(words)-1)
			word = words.pop(i)
			new.append(word)
		
		# Put it back together again
		replytext = ' '.join(new)
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
