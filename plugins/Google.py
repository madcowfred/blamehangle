# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Interface to Google, for extremely lazy people

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

GOOGLE_GOOGLE = 'GOOGLE_GOOGLE'
GOOGLE_RE = re.compile(r'^google (?P<findme>.+)$')
GOOGLE_HELP = '\02google\02 <search term> : Search via Google!'
GOOGLE_URL = 'http://www.google.com/search?q=%s'
#GOOGLE_URL = 'http://www.google.com/search?q=%s&ie=UTF-8&oe=UTF-8&hl-en&btnI=I%27m+Feeling+Lucky&meta='

RESULT_RE = re.compile('^<a href=[\'\"]?(?P<url>[^>]+)[\'\"]?>(?P<title>.+)$')
CALC_RE = re.compile('<font size=\+1><b>(?P<result>.*?)</b>')

NOBOLD_RE = re.compile('</?b>')
NOFONT_RE = re.compile('</?font[^<>]*?>')

# ---------------------------------------------------------------------------

class Google(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		google_dir = PluginTextEvent(GOOGLE_GOOGLE, IRCT_PUBLIC_D, GOOGLE_RE)
		google_msg = PluginTextEvent(GOOGLE_GOOGLE, IRCT_MSG, GOOGLE_RE)
		self.register(google_dir, google_msg)
		
		self.setHelp('google', 'google', GOOGLE_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == GOOGLE_GOOGLE:
			url = GOOGLE_URL % QuoteURL(trigger.match.group(1))
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == GOOGLE_GOOGLE:
			self.__Google(trigger, page_text)
	
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
			
			# Find the result
			chunk = FindChunk(page_text, '<!--m-->', '</a>')
			if chunk:
				# Try to match it against the regexp
				m = RESULT_RE.match(chunk)
				if not m:
					self.putlog(LOG_WARNING, 'Google page parsing failed: unable to match result')
					self.sendReply(trigger, 'Failed to match result')
					return
				
				# Build the reply string
				url = m.group('url')
				title = NOBOLD_RE.sub('', m.group('title'))
				
				replytext = '%s - %s' % (title, url)
				
				# If there was a calculation, stick that on the end
				if calc is not None:
					replytext = '%s :: %s' % (replytext, calc)
			
			# No normal result, was it the calculator?
			elif calc:
				replytext = calc
			
			# Beep, failed
			else:
				self.putlog(LOG_WARNING, 'Google page parsing failed: unable to find a result')
				self.sendReply(trigger, 'Failed to parse page')
				return
			
			# Spit out the reply
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
