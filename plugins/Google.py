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

RESULT_RE = re.compile('^<a href=[\'\"]?([^>]+)[\'\"]?>(.+)$')
NOBOLD_RE = re.compile('</?b>')

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
			url = GOOGLE_URL % trigger.match.group(1)
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == GOOGLE_GOOGLE:
			self.__Google(trigger, page_text)
	
	# -----------------------------------------------------------------------
	
	def __Google(self, trigger, page_text):
		findme = trigger.match.group(1)
		
		# Woops, no matches
		if page_text.find('No pages were found containing') >= 0:
			replytext = 'No pages were found containing "%s"' % findme
			self.sendReply(trigger, relpytext)
		
		# Some matches!
		else:
			chunk = FindChunk(page_text, '<!--m-->', '</a>')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Google page parsing failed: unable to find a result')
				self.sendReply(trigger, 'Failed to parse page')
				return
			
			m = RESULT_RE.match(chunk)
			if not m:
				self.putlog(LOG_WARNING, 'Google page parsing failed: unable to match result')
				self.sendReply(trigger, 'Failed to match result')
				return
			
			url = m.group(1)
			title = NOBOLD_RE.sub('', m.group(2))
			
			replytext = '%s - %s' % (title, url)
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
