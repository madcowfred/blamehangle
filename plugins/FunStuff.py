# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# A collection of silly things for people to play with.

import random
import re
import time

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------
# This regexp needs fixing in the year 3000, don't forget
FUN_EASTER = 'FUN_EASTER'
EASTER_HELP = '\02easter\02 <year> : Work out what day Easter Sunday falls on for a given year.'
EASTER_RE = re.compile('^easter (?P<year>[12]\d\d\d)$')

FUN_EIGHTBALL = 'FUN_EIGHTBALL'
EIGHTBALL_HELP = '\028ball\02 <question> : The magic 8 ball will answer your question!'
EIGHTBALL_RE = re.compile('^8ball (?P<question>.+)$')

FUN_MUDDLE = 'FUN_MUDDLE'
MUDDLE_HELP = '\02muddle\02 <text> : Muddles your text by rearranging words.'
MUDDLE_RE = re.compile('^muddle (?P<text>.+)$')

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
		self.setTextEvent(FUN_EASTER, EASTER_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_EIGHTBALL, EIGHTBALL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_MUDDLE, MUDDLE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('funstuff', 'easter', EASTER_HELP)
		self.setHelp('funstuff', '8ball', EIGHTBALL_HELP)
		self.setHelp('funstuff', 'muddle', MUDDLE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Work out what date Easter Sunday falls on for a given year.
	def _trigger_FUN_EASTER(self, trigger):
		y = int(trigger.match.group('year'))
		
		# Taken from http://aa.usno.navy.mil/faq/docs/easter.html
		c = y / 100
		n = y - 19 * ( y / 19 )
		k = ( c - 17 ) / 25
		i = c - c / 4 - ( c - k ) / 3 + 19 * n + 15
		i = i - 30 * ( i / 30 )
		i = i - ( i / 28 ) * ( 1 - ( i / 28 ) * ( 29 / ( i + 1 ) ) * ( ( 21 - n ) / 11 ) )
		j = y + y / 4 + i + 2 - c + c / 4
		j = j - 7 * ( j / 7 )
		l = i - j
		m = 3 + ( l + 40 ) / 44
		d = l + 28 - 31 * ( m / 4 )
		
		# Get a useful sort of time value out of that
		temp_date = '%04d %02d %02d' % (y, m, d)
		try:
			t = time.strptime(temp_date, '%Y %m %d')
		
		except ValueError:
			replytext = 'Failed to parse date, uh-oh'
		
		else:
			# If it was previous, use was
			now = time.time()
			then = time.mktime(t)
			
			if now > then:
				replytext = time.strftime('Easter Sunday was on %B %d in %Y', t)
			else:
				replytext = time.strftime('Easter Sunday will be on %B %d in %Y', t)
		
		self.sendReply(trigger, replytext)
	
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
