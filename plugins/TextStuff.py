# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Miscellaneous commands for playing with text.'

import md5
import re
import sha
import urllib
import zlib

#from classes.Common import *
#from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class TextStuff(Plugin):
	def setup(self):
		# Build the ROT13 translation table
		chars = [chr(i) for i in range(256)]
		
		for i in range(0, 26):
			j = (i + 13) % 26
			# A-Z
			chars[j+65] = chr(i+65)
			# a-z
			chars[j+97] = chr(i+97)
		
		self.__trans_ROT13 = ''.join(chars)
	
	def register(self):
		self.addTextEvent(
			method = self.__CRC32,
			regexp = re.compile('^crc32 (?P<text>.+)$'),
			help = ('text', 'crc32', '\02crc32\02 <text> : Compute the CRC32 checksum of text.'),
		)
		self.addTextEvent(
			method = self.__MD5,
			regexp = re.compile('^md5 (?P<text>.+)$'),
			help = ('text', 'md5', '\02md5\02 <text> : Compute the MD5 checksum of text.'),
		)
		self.addTextEvent(
			method = self.__ROT13,
			regexp = re.compile('^rot13 (?P<text>.+)$'),
			help = ('text', 'rot13', '\02rot13\02 <text> : ROT13 text.'),
		)
		self.addTextEvent(
			method = self.__SHA1,
			regexp = re.compile('^sha1 (?P<text>.+)$'),
			help = ('text', 'sha1', '\02sha1\02 <text> : Compute the SHA-1 checksum of text.'),
		)
		self.addTextEvent(
			method = self.__QuoteURL,
			regexp = re.compile('^quoteurl (?P<text>.+)$'),
			help = ('text', 'quoteurl', '\02quoteurl\02 <url> : Quote URL?'),
		)
		self.addTextEvent(
			method = self.__UnquoteURL,
			regexp = re.compile('^unquoteurl (?P<text>.+)$'),
			help = ('text', 'unquoteurl', '\02unquoteurl\02 <url> : Unquote URL?'),
		)
	
	# ---------------------------------------------------------------------------
	# Compute the CRC32 checksum of some text
	def __CRC32(self, trigger):
		text = trigger.match.group('text')
		# Vileness to stop the warning from coming up
		replytext = '%08X' % (zlib.crc32(text) & 2**32L - 1)
		self.sendReply(trigger, replytext)
	# Compute the MD5 checksum of some text
	def __MD5(self, trigger):
		text = trigger.match.group('text')
		replytext = md5.new(text).hexdigest()
		self.sendReply(trigger, replytext)
	# ROT13 some text
	def __ROT13(self, trigger):
		text = trigger.match.group('text')
		replytext = text.translate(self.__trans_ROT13)
		self.sendReply(trigger, replytext)
	# Compute the SHA1 checksum of some text
	def __SHA1(self, trigger):
		text = trigger.match.group('text')
		replytext = sha.new(text).hexdigest()
		self.sendReply(trigger, replytext)
	# URL quote some text?
	def __QuoteURL(self, trigger):
		text = trigger.match.group('text')
		replytext = urllib.quote(text, ':/?&=')
		self.sendReply(trigger, replytext)
	# URL unquote some text?
	def __UnquoteURL(self, trigger):
		text = trigger.match.group('text')
		replytext = urllib.unquote(text)
		self.sendReply(trigger, replytext)
	
# ---------------------------------------------------------------------------
