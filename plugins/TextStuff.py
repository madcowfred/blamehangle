# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Miscellaneous commands for playing with text.'

import md5
import re
import sha
import urllib
import zlib

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

TEXT_CRC32 = 'TEXT_CRC32'
CRC32_HELP = '\02crc32\02 <text> : Compute the CRC32 checksum of text.'
CRC32_RE = re.compile('^crc32 (?P<text>.+)$')

TEXT_MD5 = 'TEXT_MD5'
MD5_HELP = '\02md5\02 <text> : Compute the MD5 checksum of text.'
MD5_RE = re.compile('^md5 (?P<text>.+)$')

TEXT_ROT13 = 'TEXT_ROT13'
ROT13_HELP = '\02rot13\02 <text> : ROT13 text.'
ROT13_RE = re.compile('^rot13 (?P<text>.+)$')

TEXT_SHA1 = 'TEXT_SHA1'
SHA1_HELP = '\02sha1\02 <text> : Compute the SHA-1 checksum of text.'
SHA1_RE = re.compile('^sha1 (?P<text>.+)$')

TEXT_URLDEC = 'TEXT_URLDEC'
URLDEC_HELP = '\02urldec\02 <url> : Do something else.'
URLDEC_RE = re.compile('^urldec (?P<text>.+)$')

TEXT_URLENC = 'TEXT_URLENC'
URLENC_HELP = '\02urlenc\02 <url> : Do something.'
URLENC_RE = re.compile('^urlenc (?P<text>.+)$')

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
		
		self.__ROT13 = ''.join(chars)
	
	def register(self):
		self.setTextEvent(TEXT_CRC32, CRC32_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(TEXT_MD5, MD5_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(TEXT_ROT13, ROT13_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(TEXT_SHA1, SHA1_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(TEXT_URLDEC, URLDEC_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(TEXT_URLENC, URLENC_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('text', 'crc32', CRC32_HELP)
		self.setHelp('text', 'md5', MD5_HELP)
		self.setHelp('text', 'rot13', ROT13_HELP)
		self.setHelp('text', 'sha1', SHA1_HELP)
		self.setHelp('text', 'urldec', URLDEC_HELP)
		self.setHelp('text', 'urlenc', URLENC_HELP)
		self.registerHelp()
	
	# ---------------------------------------------------------------------------
	
	def _trigger_TEXT_CRC32(self, trigger):
		text = trigger.match.group('text')
		# Vileness to stop the warning from coming up
		replytext = '%08X' % (zlib.crc32(text) & 2**32L - 1)
		self.sendReply(trigger, replytext)
	
	def _trigger_TEXT_MD5(self, trigger):
		text = trigger.match.group('text')
		replytext = md5.new(text).hexdigest()
		self.sendReply(trigger, replytext)
	
	def _trigger_TEXT_ROT13(self, trigger):
		text = trigger.match.group('text')
		replytext = text.translate(self.__ROT13)
		self.sendReply(trigger, replytext)
	
	def _trigger_TEXT_SHA1(self, trigger):
		text = trigger.match.group('text')
		replytext = sha.new(text).hexdigest()
		self.sendReply(trigger, replytext)
	
	def _trigger_TEXT_URLDEC(self, trigger):
		text = trigger.match.group('text')
		replytext = urllib.unquote(text)
		self.sendReply(trigger, replytext)
	
	def _trigger_TEXT_URLENC(self, trigger):
		text = trigger.match.group('text')
		replytext = urllib.quote(text, ':/?&=')
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
