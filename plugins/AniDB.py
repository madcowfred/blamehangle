# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Asks AniDB.net for information about anime.

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

ANIDB = 'ANIDB'
ANIDB_HELP = '\02anidb\02 <name> : Search for anime information on AniDB.'
ANIDB_RE = re.compile(r'^anidb (?P<findme>.+)$')

ANIDB_URL = "http://anidb.ath.cx/perl-bin/animedb.pl?show=animelist&noalias=1&adb.search=%s"

RESULT_RE = re.compile(r'^(\d+)">(?:<i>|)(.*?)(?:</i>|)$')
TEMP_RE = re.compile(r'^!anidb (?P<findme>.+)$')

# ---------------------------------------------------------------------------

class AniDB(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		anidb_dir = PluginTextEvent(ANIDB, IRCT_PUBLIC_D, ANIDB_RE)
		anidb_msg = PluginTextEvent(ANIDB, IRCT_MSG, ANIDB_RE)
		self.register(anidb_dir, anidb_msg)
		
		self.setHelp('anidb', 'anidb', ANIDB_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == 'ANIDB':
			url = ANIDB_URL % quote(trigger.match.group('findme').lower())
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == 'ANIDB':
			self.__AniDB(trigger, page_text)
	
	# ---------------------------------------------------------------------------
	# Parse the page, finding the information we need.
	def __AniDB(self, trigger, page_text):
		findme = trigger.match.group('findme').lower()
		
		# If it's search results, parse them and spit them out
		if page_text.find('Search for:') >= 0:
			# We need some results, damn you
			chunks = FindChunks(page_text, '<a href="animedb.pl?show=anime&aid=', '</a>')
			if not chunks:
				replytext = 'No results found for "%s"' % findme
				self.sendReply(trigger, replytext)
				return
			
			# See if any of them match our regexp
			results = []
			
			for chunk in chunks:
				m = RESULT_RE.match(chunk)
				if m:
					result = '\x02[\x02%s\x02]\x02' % m.group(2)
					results.append(result)
			
			# Spit them out
			if len(results) > 5:
				replytext = 'There were \002%s\002 results, first 5 :: %s' % (len(results), ' '.join(results[:5]))
			else:
				replytext = 'There were \002%s\002 results :: %s' % (len(results), ' '.join(results))
			
			self.sendReply(trigger, replytext)
		
		# If it's an anime page, parse it and spit the info out
		elif page_text.find('Show Anime - ') >= 0:
			parts = []
			
			# Find the info we want
			for thing in ('Title', 'Genre', 'Type', 'Episodes', 'Year', 'Producer', 'Rating'):
				chunk = FindChunk(page_text, '%s:' % thing, '</tr>')
				if chunk:
					lines = StripHTML(chunk)
					if lines:
						if lines[0] == '-':
							info = '?'
						else:
							# Special crap for Genre
							n = lines[0].find(' - ')
							if n >= 0:
								info = lines[0][:n]
							else:
								info = lines[0]
					else:
						info = '?'
				else:
					info = '?'
				
				part = '\x02[\x02%s: %s\x02]\x02' % (thing, info)
				parts.append(part)
			
			# Find our aid
			m = re.search(r'aid=(\d+)', page_text)
			if m:
				url = 'http://anidb.ath.cx/perl-bin/animedb.pl?show=anime&aid=%s' % m.group(1)
			else:
				url = '?'
			
			part = '\x02[\x02URL: %s\x02]\x02' % url
			parts.append(part)
			
			# Spit it out
			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
