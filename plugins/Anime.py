# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Various bits and pieces for looking up anime information.'

import asyncore
import re
import socket

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

ANIME_ANIDB = 'ANIME_ANIDB'
ANIDB_HELP = '\02anidb\02 <name> : Search for anime information on AniDB.'
ANIDB_RE = re.compile(r'^anidb (?P<findme>.+)$')

ANIDB_URL = "http://anidb.ath.cx/perl-bin/animedb.pl?show=animelist&noalias=1&adb.search=%s"
AID_URL = 'http://anidb.ath.cx/perl-bin/animedb.pl?show=anime&aid=%s'

RESULT_RE = re.compile(r'^(\d+)">(?:<i>|)(.*?)(?:</i>|)$')

# ---------------------------------------------------------------------------

ANIME_ANIMENFO = 'ANIME_ANIMENFO'
ANIMENFO_HELP = '\02animenfo\02 <name> : Search for anime information on AnimeNFO.'
ANIMENFO_RE = re.compile(r'^animenfo (?P<findme>.+)$')

ANIMENFO_FIELDS = {
	'TITLE': 'Title',
	'CATEGORY': 'Category',
	'TOTAL': 'Total',
	'GENRE': 'Genre',
	'YEAR': 'Year',
	'STUDIO': 'Studio',
	'USDISTRO': 'US Distribution',
	'RATING': 'Rating',
	'LINK': 'Link',
}

ANIMENFO_ERRORS = {
	'1': 'Empty query string',
	'2': 'Database error',
	'3': 'Unexpected error',
}

ANIMENFO_HOST = 'misha.project-on.net'
ANIMENFO_PORT = 3000
ANIMENFO_SEND = '<ANIME><TITLE>%s</TITLE><FIELD>TITLE CATEGORY TOTAL GENRE YEAR STUDIO USDISTRO RATING LINK</FIELD></ANIME>'

# ---------------------------------------------------------------------------

class Anime(Plugin):
	def register(self):
		self.setTextEvent(ANIME_ANIDB, ANIDB_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(ANIME_ANIMENFO, ANIMENFO_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('anime', 'anidb', ANIDB_HELP)
		self.setHelp('anime', 'animenfo', ANIMENFO_HELP)
		self.registerHelp()
	
	# ---------------------------------------------------------------------------
	
	def _trigger_ANIME_ANIDB(self, trigger):
		url = ANIDB_URL % QuoteURL(trigger.match.group('findme').lower())
		self.urlRequest(trigger, self.__Parse_AniDB, url)
	
	def _trigger_ANIME_ANIMENFO(self, trigger):
		async_animenfo(self, trigger)
	
	# ---------------------------------------------------------------------------
	# Parse an AniDB page
	def __Parse_AniDB(self, trigger, page_text):
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
					name = m.group(2)
					
					# If it's an exact match for what we're looking for, grab it
					if name.lower() == findme:
						url = AID_URL % m.group(1)
						self.urlRequest(trigger, self.__Parse_AniDB, url)
						return
					
					result = '\x02[\x02%s\x02]\x02' % m.group(2)
					results.append(result)
			
			# Spit them out
			if len(results) > 10:
				replytext = 'There were \002%s\002 results, first 10 :: %s' % (len(results), ' '.join(results[:10]))
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
			m = re.search(r'name="aid" value="(\d+)"', page_text)
			if m:
				url = AID_URL % m.group(1)
			else:
				url = '?'
			
			part = '\x02[\x02URL: %s\x02]\x02' % url
			parts.append(part)
			
			# Spit it out
			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
		
		# Adult content, pfft
		elif page_text.find('Adult Content Warning'):
			self.sendReply(trigger, "Seems to be hentai, you'll need an AniDB user account to see the details :(")
		
		# Parsing failed
		else:
			self.sendReply(trigger, 'Page parsing failed.')
	
	# ---------------------------------------------------------------------------
	# Parse the output of an AnimeNFO query
	def Parse_AnimeNFO(self, trigger, data):
		data = data.replace('\n', '').strip()
		if data:
			m = re.match('^<OUTPUT>(.+)</OUTPUT>$', data, re.S)
			if m:
				# Split into field,value pairs
				fields = re.findall(r'<(.+)>(.+)</\1>', m.group(1))
				
				field, value = fields[0]
				
				if field == 'ERROR':
					errortext = ANIMENFO_ERRORS.get(value, 'Unknown error')
					replytext = 'AnimeNFO returned error: %s' % errortext
				
				elif field == 'RESULT':
					if value == '0':
						replytext = 'No matches found.'
					
					elif value == '1':
						chunks = []
						for field, value in fields[1:]:
							chunk = '\02[\02%s: %s\02]\02' % (ANIMENFO_FIELDS[field], value)
							chunks.append(chunk)
						
						replytext = ' - '.join(chunks)
					
					else:
						items = ['"%s"' % v for f, v in fields[1:]]
						items.sort()
						
						replytext = 'Found \02%d\02 results: ' % (len(items))
						replytext += ', '.join(items)
				
				else:
					replytext = 'Unable to parse AnimeNFO output.'
			
			else:
				replytext = 'Unable to parse AnimeNFO output.'
		
		else:
			replytext = 'No data returned.'
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------

class async_animenfo(asyncore.dispatcher_with_send):
	def __init__(self, parent, trigger):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.data = ''
		self.status = 0
		
		self.parent = parent
		self.trigger = trigger
		
		# Create the socket
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		
		# Try to connect. It seems this will blow up if it can't resolve the
		# host.
		try:
			self.connect((ANIMENFO_HOST, ANIMENFO_PORT))
		except socket.gaierror, msg:
			tolog = "Error while trying to visit AnimeNFO: %s - %s" % (self.url, msg)
			self.parent.putlog(LOG_WARNING, tolog)
			self.close()
	
	def handle_connect(self):
		pass
	
	def handle_read(self):
		data = self.recv(2048)
		
		# Welcome message
		if self.status == 0:
			self.status = 1
			tosend = ANIMENFO_SEND % self.trigger.match.group('findme')
			self.send(tosend)
		
		# Data!
		else:
			self.data += data
	
	def handle_close(self):
		self.parent.Parse_AnimeNFO(self.trigger, self.data)
		
		self.close()

# ---------------------------------------------------------------------------
