# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'A collection of silly things for people to play with.'

import random
import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

# This regexp needs fixing in the year 3000, don't forget
FUN_EASTER = 'FUN_EASTER'
EASTER_HELP = '\02easter\02 <year> : Work out what day Easter Sunday falls on for a given year.'
EASTER_RE = re.compile('^easter (?P<year>\d{1,4})$')

FUN_EIGHTBALL = 'FUN_EIGHTBALL'
EIGHTBALL_HELP = '\028ball\02 <question> : The magic 8 ball will answer your question!'
EIGHTBALL_RE = re.compile('^8ball (?P<question>.+)$')

FUN_MUDDLE = 'FUN_MUDDLE'
MUDDLE_HELP = '\02muddle\02 <text> : Muddles your text by rearranging words.'
MUDDLE_RE = re.compile('^muddle (?P<text>.+)$')


FUN_HORO = 'FUN_HORO'
HORO_HELP = "\02horo\02 <sign> : Look up today's horoscope for <sign>."
HORO_RE = re.compile('^horo (?P<sign>\S+)$')
HORO_URL = 'http://astrology.yahoo.com/astrology/general/dailyoverview/%s'

HORO_SIGNS = ('aquarius', 'aries', 'cancer', 'capricorn', 'gemini', 'leo', 'libra',
	'pisces', 'sagittarius', 'scorpio', 'taurus', 'virgo')

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
	
	# ---------------------------------------------------------------------------
	
	def register(self):
		self.setTextEvent(FUN_EASTER, EASTER_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_EIGHTBALL, EIGHTBALL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_HORO, HORO_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(FUN_MUDDLE, MUDDLE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('funstuff', 'easter', EASTER_HELP)
		self.setHelp('funstuff', '8ball', EIGHTBALL_HELP)
		self.setHelp('funstuff', 'horo', HORO_HELP)
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
		easter_date = '%04d%02d%02d' % (y, m, d)
		now_date = time.strftime('%Y%m%d')
		
		month = ('January', 'February', 'March', 'April', 'May', 'June',
			'July', 'August', 'September', 'October', 'November', 'December')
		
		if now_date > easter_date:
			replytext = 'Easter Sunday was on %s %02d, %d AD' % (month[m-1], d, y)
		else:
			replytext = 'Easter Sunday will be on %s %02d, %d AD' % (month[m-1], d, y)
		
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
	
	# -----------------------------------------------------------------------
	# Get today's horoscope
	def _trigger_FUN_HORO(self, trigger):
		sign = trigger.match.group('sign').lower()
		if sign in HORO_SIGNS:
			url = HORO_URL % sign
			self.urlRequest(trigger, self.__Horoscope, url)
		else:
			replytext = "'%s' is not a valid sign!" % sign
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse a Yahoo Astrology page
	def __Horoscope(self, trigger, resp):
		# Find the sign
		sign = FindChunk(resp.data, '<big class="yastshsign">', '</big>')
		if not sign:
			self.sendReply(trigger, 'Page parsing failed: sign.')
			return
		
		# Find the data
		chunk = FindChunk(resp.data, 'Quickie:', '</td>')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: data.')
			return
		
		# Parse the bits we want
		bits = StripHTML(chunk)
		if len(bits) != 2:
			self.sendReply(trigger, 'Page parsing failed: bits.')
			return
		
		if bits[1].startswith('Overview:'):
			bits[1] = bits[1][9:]
		
		replytext = 'Horoscope for %s :: \02[\02Quickie: %s\02]\02 \02[\02Overview: %s\02]\02' % (sign, bits[0].strip(), bits[1].strip())
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
