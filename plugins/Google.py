# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Lets lazy people use Google from IRC.'

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

GOOGLE_GOOGLE = 'GOOGLE_GOOGLE'
GOOGLE_HELP = '\02google\02 <search term> : Search via Google!'
GOOGLE_RE = re.compile(r'^google (?P<findme>.+)$')
GOOGLE_URL = 'http://www.google.com/search?q=%s&num=5'

RESULT_RE = re.compile('^<a href=[\'\"]?(?P<url>[^>]+)[\'\"]?>(?P<title>.+)$')
CALC_RE = re.compile('<font size=\+1><b>(?P<result>.*?)</b>')

NOBOLD_RE = re.compile('</?b>')
NOFONT_RE = re.compile('</?font[^<>]*?>')

# ---------------------------------------------------------------------------

GOOGLE_TRANSLATE = 'GOOGLE_TRANSLATE'
TRANSLATE_HELP = '\02translate\02 <from> \02to\02 <to> <text> : Translate some text via Google Translate.'
TRANSLATE_RE = re.compile('^translate (?P<from>\S+)(?: to | )(?P<to>\S+) (?P<text>.+)$')
TRANSLATE_URL = 'http://translate.google.com/translate_t?langpair=%s|%s&text=%s'

GOOGLE_TRANSMANGLE = 'GOOGLE_TRANSMANGLE'
TRANSMANGLE_HELP = '\02transmangle\02 <lang> <text> : Mangle text by translating from English to lang and back again.'
TRANSMANGLE_RE = re.compile('^transmangle (?P<lang>\S+) (?P<text>.+)$')

# A mapping of language translations we can do
LANG_MAP = {
	'de': ('en', 'fr'),
	'en': ('de', 'es', 'fr', 'it', 'pt'),
	'es': ('en',),
	'fr': ('de', 'en'),
	'it': ('en',),
	'pt': ('en',),
}

# ---------------------------------------------------------------------------

class Google(Plugin):
	def register(self):
		self.setTextEvent(GOOGLE_GOOGLE, GOOGLE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(GOOGLE_TRANSLATE, TRANSLATE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(GOOGLE_TRANSMANGLE, TRANSMANGLE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('google', 'google', GOOGLE_HELP)
		self.setHelp('google', 'translate', TRANSLATE_HELP)
		self.setHelp('google', 'transmangle', TRANSMANGLE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _trigger_GOOGLE_GOOGLE(self, trigger):
		url = GOOGLE_URL % QuoteURL(trigger.match.group(1))
		self.urlRequest(trigger, self.__Google, url)
	
	def _trigger_GOOGLE_TRANSLATE(self, trigger):
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
		
	def _trigger_GOOGLE_TRANSMANGLE(self, trigger):
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
		trigger.done = 0
		
		url = TRANSLATE_URL % ('en', _lang, quote(_text))
		self.urlRequest(trigger, self.__Transmangle, url)
	
	# -----------------------------------------------------------------------
	
	def __Google(self, trigger, page_url, page_text):
		findme = trigger.match.group(1)
		
		# Woops, no matches
		if page_text.find('- did not match any documents') >= 0:
			replytext = 'No pages were found containing "%s"' % findme
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			page_text = UnquoteHTML(page_text)
			
			# Go go calculator
			m = CALC_RE.search(page_text)
			if m:
				calc = '%s' % NOFONT_RE.sub('', m.group('result'))
			else:
				calc = None
			
			# Find the result(s)
			chunks = FindChunks(page_text, '<!--m-->', '</a>')
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
						trigger.event.IRCType == IRCT_MSG:
						
						for title, url in results[1:]:
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
	
	def __Translate(self, trigger, page_url, page_text):
		# Couldn't translate
		if page_text.find('Sorry, this text could not be translated') >= 0:
			replytext = 'Sorry, this text could not be translated.'
		
		# Did translate!
		else:
			chunk = FindChunk(page_text, 'wrap=PHYSICAL>', '</textarea>')
			if chunk:
				replytext = chunk
			else:
				replytext = 'Unable to parse page.'
		
		# Spit out our answer
		self.sendReply(trigger, replytext)
	
	def __Transmangle(self, trigger, page_url, page_text):
		replytext = None
		
		# Couldn't translate
		if page_text.find('Sorry, this text could not be translated') >= 0:
			replytext = 'Sorry, this text could not be translated.'
		
		else:
			chunk = FindChunk(page_text, 'wrap=PHYSICAL>', '</textarea>')
			if chunk:
				# We need to translate it back again now
				if trigger.done == 0:
					trigger.done = 1
					
					_lang = trigger.match.group('lang').lower()
					_text = trigger.match.group('text')
					
					url = TRANSLATE_URL % (_lang, 'en', quote(chunk))
					self.urlRequest(trigger, self.__Transmangle, url)
				
				# Now we're done
				else:
					replytext = chunk
			
			else:
				replytext = 'Unable to parse page.'
		
		# Spit something out if we have to
		if replytext is not None:
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
