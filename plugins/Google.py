# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Interface to Google, for extremely lazy people

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

GOOGLE_GOOGLE = 'GOOGLE_GOOGLE'
GOOGLE_RE = re.compile(r'^google (?P<findme>.+)$')
GOOGLE_HELP = '\02google\02 <search term> : Search via Google!'
GOOGLE_URL = 'http://www.google.com/search?q=%s&num=5'

RESULT_RE = re.compile('^<a href=[\'\"]?(?P<url>[^>]+)[\'\"]?>(?P<title>.+)$')
CALC_RE = re.compile('<font size=\+1><b>(?P<result>.*?)</b>')

NOBOLD_RE = re.compile('</?b>')
NOFONT_RE = re.compile('</?font[^<>]*?>')


GOOGLE_TRANSLATE = 'GOOGLE_TRANSLATE'
TRANSLATE_HELP = '\02translate\02 <from> \02to\02 <to> <text> : Translate some text via Google Translate.'
TRANSLATE_RE = re.compile('^translate (?P<from>\S+)(?: to | )(?P<to>\S+) (?P<text>.+)$')

TRANSLATE_URL = 'http://translate.google.com/translate_t?langpair=%s|%s&text=%s'

# ---------------------------------------------------------------------------
# The different languages we know about
LANGUAGES = {
	'de': 'German',
	'en': 'English',
	'es': 'Spanish',
	'fr': 'French',
	'it': 'Italian',
	'pt': 'Portuguese',
}

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
	def _message_PLUGIN_REGISTER(self, message):
		google_dir = PluginTextEvent(GOOGLE_GOOGLE, IRCT_PUBLIC_D, GOOGLE_RE)
		google_msg = PluginTextEvent(GOOGLE_GOOGLE, IRCT_MSG, GOOGLE_RE)
		translate_dir = PluginTextEvent(GOOGLE_TRANSLATE, IRCT_PUBLIC_D, TRANSLATE_RE)
		translate_msg = PluginTextEvent(GOOGLE_TRANSLATE, IRCT_MSG, TRANSLATE_RE)
		self.register(google_dir, google_msg, translate_dir, translate_msg)
		
		self.setHelp('google', 'google', GOOGLE_HELP)
		self.setHelp('google', 'translate', TRANSLATE_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == GOOGLE_GOOGLE:
			url = GOOGLE_URL % QuoteURL(trigger.match.group(1))
			self.urlRequest(trigger, url)
		
		elif trigger.name == GOOGLE_TRANSLATE:
			_from = trigger.match.group('from').lower()
			_to = trigger.match.group('to').lower()
			_text = trigger.match.group('text').lower()
			
			replytext = None
			
			# Verify our parameters
			if not LANGUAGES.has_key(_from):
				replytext = '"%s" is not a valid language!' % _from
			elif not LANGUAGES.has_key(_to):
				replytext = '"%s" is not a valid language!' % _to
			elif _to not in LANG_MAP[_from]:
				replytext = '"%s" to "%s" is not a valid translation!' % (_from, _to)
			elif len(_text) > 200:
				replytext = 'Text is too long!'
			
			# If we have a reply, bail now
			if replytext is not None:
				self.sendReply(trigger, replytext)
				return
			
			# Otherwise, build the URL and send it off
			url = TRANSLATE_URL % (_from, _to, quote(_text))
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == GOOGLE_GOOGLE:
			self.__Google(trigger, page_text)
		
		elif trigger.name == GOOGLE_TRANSLATE:
			self.__Translate(trigger, page_text)
	
	# -----------------------------------------------------------------------
	
	def __Google(self, trigger, page_text):
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
	
	def __Translate(self, trigger, page_text):
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

# ---------------------------------------------------------------------------
