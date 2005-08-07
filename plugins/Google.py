# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
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

'Lets lazy people use Google from IRC.'

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

GOOGLE_URL = 'http://www.google.com/search?q=%s'

RESULT_RE = re.compile('^<a href="(?P<url>[^>]*?)"[^>]*>(?P<title>.+)$')
CALC_RE = re.compile('<font size=\+1><b>(?P<result>.*?)</b>')

NOBOLD_RE = re.compile('</?b>')
NOFONT_RE = re.compile('</?font[^<>]*?>')

# ---------------------------------------------------------------------------
TRANSLATE_URL = 'http://translate.google.com/translate_t?langpair=%s|%s&text=%s'

# A mapping of language translations we can do
LANG_MAP = {
	'de': ('en', 'fr'),
	'en': ('de', 'es', 'fr', 'it', 'pt'),
	'es': ('en',),
	'fr': ('de', 'en'),
	'it': ('en',),
	'pt': ('en',),
}

TRANSMANGLE_LIMIT = 8

# ---------------------------------------------------------------------------

class Google(Plugin):
	_HelpSection = 'google'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_Google,
			regexp = r'^google (?P<findme>.+)$',
			help = ('google', '\02google\02 <search term> : Search via Google!'),
		)
		self.addTextEvent(
			method = self.__Fetch_Translate,
			regexp = r'^translate (?P<from>\S+)(?: to | )(?P<to>\S+) (?P<text>.+)$',
			help = ('translate', '\02translate\02 <from> \02to\02 <to> <text> : Translate some text via Google Translate.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Transmangle,
			regexp = r'^transmangle (?P<lang>\S+) (?P<text>.+)$',
			help = ('transmangle', '\02transmangle\02 <lang> <text> : Mangle text by translating from English to lang and back again.'),
		)
	
	# -----------------------------------------------------------------------
	
	def __Fetch_Google(self, trigger):
		url = GOOGLE_URL % QuoteURL(trigger.match.group(1))
		self.urlRequest(trigger, self.__Google, url)
	
	def __Fetch_Translate(self, trigger):
		_from = trigger.match.group('from').lower()
		_to = trigger.match.group('to').lower()
		_text = trigger.match.group('text')
		
		replytext = None
		
		# Verify our parameters
		if not LANG_MAP.has_key(_from):
			replytext = '"%s" is not a valid language!' % _from
		elif not LANG_MAP.has_key(_to):
			replytext = '"%s" is not a valid language!' % _to
		elif _to not in LANG_MAP[_from]:
			replytext = '"%s" to "%s" is not a valid translation!' % (_from, _to)
		elif len(_text) > 300:
			replytext = 'Text is too long! %d > 300' % (len(_text))
		
		# If we have a reply, bail now
		if replytext is not None:
			self.sendReply(trigger, replytext)
			return
		
		# Otherwise, build the URL and send it off
		url = TRANSLATE_URL % (_from, _to, quote(_text))
		self.urlRequest(trigger, self.__Translate, url)
		
	def __Fetch_Transmangle(self, trigger):
		_lang = trigger.match.group('lang').lower()
		_text = trigger.match.group('text')
		
		replytext = None
		
		# Verify our parameters
		if _lang == 'en':
			replytext = "Can't translate from English to English!"
		elif not LANG_MAP.has_key(_lang):
			replytext = '"%s" is not a valid language!' % _lang
		elif len(_text) > 300:
			replytext = 'Text is too long! %d > 300' % (len(_text))
		
		# If we have a reply, bail now
		if replytext is not None:
			self.sendReply(trigger, replytext)
			return
		
		# Otherwise, build the URL and send it off
		trigger._round = 1
		trigger._lang = _lang
		trigger._text = [_text,]
		
		url = TRANSLATE_URL % ('en', _lang, quote(_text))
		self.urlRequest(trigger, self.__Transmangle, url)
	
	# -----------------------------------------------------------------------
	
	def __Google(self, trigger, resp):
		findme = trigger.match.group(1)
		
		# Woops, no matches
		if resp.data.find('- did not match any documents') >= 0:
			replytext = 'No pages were found containing "%s"' % findme
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			data = UnquoteHTML(resp.data)
			
			# Go go calculator
			m = CALC_RE.search(data)
			if m:
				calc = '%s' % NOFONT_RE.sub('', m.group('result'))
				calc = calc.replace('&times;', '*')
				calc = calc.replace('<sup>', '^')
				calc = calc.replace('</sup>', '')
			else:
				calc = None
			
			# Find the result(s)
			chunks = FindChunks(data, '<!--m-->', '</a>')
			if chunks:
				results = []
				
				for chunk in chunks:
					# Try to match it against the regexp
					m = RESULT_RE.match(chunk)
					if not m:
						continue
					
					title = NOBOLD_RE.sub('', m.group('title'))
					url = m.group('url')
					
					# Try to filter out annoying multiple URLs
					if [u for t, u in results if url.startswith(u)]:
						continue
					
					# Fix up evil annoying URLs
					if url.startswith('/url'):
						for chunk in url.split('&'):
							if chunk.startswith('q='):
								url = chunk[2:]
								break
					
					# Keep the result
					results.append([title, url])
				
				# If we found some results, spit them out
				if results:
					# Add calculator output to the first result
					if calc:
						replytext = '%s :: %s - %s' % (calc, results[0][0], results[0][1])
					else:
						replytext = '%s - %s' % (results[0][0], results[0][1])
					self.sendReply(trigger, replytext)
					
					# If that user is trustworthy, or we're in private, spam the rest
					if self.Userlist.Has_Flag(trigger.userinfo, 'Google', 'spam') or \
						trigger.IRCType == IRCT_MSG:
						
						for title, url in results[1:5]:
							replytext = '%s - %s' % (title, url)
							self.sendReply(trigger, replytext)
				
				# If we found no results at all, cry
				else:
					self.putlog(LOG_WARNING, 'Google page parsing failed: unable to match result')
					self.sendReply(trigger, 'Failed to match result')
					return
			
			# No normal result, was it the calculator?
			elif calc:
				self.sendReply(trigger, calc)
			
			# Beep, failed
			else:
				self.putlog(LOG_WARNING, 'Google page parsing failed: unable to find a result')
				self.sendReply(trigger, 'Failed to parse page')
				return
	
	# -----------------------------------------------------------------------
	
	def __Translate(self, trigger, resp):
		# Couldn't translate
		if resp.data.find('Sorry, this text could not be translated') >= 0:
			replytext = 'Sorry, this text could not be translated.'
		
		# Did translate!
		else:
			chunk = FindChunk(resp.data, 'wrap=PHYSICAL>', '</textarea>')
			if chunk:
				replytext = chunk
			else:
				replytext = 'Unable to parse page.'
		
		# Spit out our answer
		self.sendReply(trigger, replytext)
	
	def __Transmangle(self, trigger, resp):
		replytext = None
		
		# Couldn't translate
		if resp.data.find('Sorry, this text could not be translated') >= 0:
			replytext = 'Sorry, this text could not be translated.'
		
		# Maybe loop again now
		else:
			chunk = FindChunk(resp.data, 'wrap=PHYSICAL>', '</textarea>')
			if chunk:
				# Needs to be translated again
				if (trigger._round % 2) == 1:
					trigger._round += 1
					
					url = TRANSLATE_URL % (trigger._lang, 'en', quote(chunk))
					self.urlRequest(trigger, self.__Transmangle, url)
				
				# We're back in English
				else:
					# And we're done
					if trigger._round == TRANSMANGLE_LIMIT or chunk in trigger._text:
						replytext = chunk
					
					else:
						trigger._round += 1
						trigger._text.append(chunk)
						
						url = TRANSLATE_URL % ('en', trigger._lang, quote(chunk))
						self.urlRequest(trigger, self.__Transmangle, url)
			
			# It's back in English
			else:
				replytext = 'Unable to parse page!'
		
		# Spit something out if we have to
		if replytext is not None:
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
