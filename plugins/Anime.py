# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Various bits and pieces for looking up anime information.'

import re
import socket

from classes.async_buffered import buffered_dispatcher

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

ANIDB_URL = "http://anidb.info/perl-bin/animedb.pl?show=animelist&adb.search=%s"
AID_URL = 'http://anidb.info/perl-bin/animedb.pl?show=anime&aid=%s'

# Urgh.
ANIDB_AKA_RE = re.compile(r'^(\d+)"><i>(.*?)</i></a>\s*<small>.*?aid=(\d+)" class="tiny">(.*?)</a>')
ANIDB_RESULT_RE = re.compile(r'^(\d+)">(.*?)</a>')

# ---------------------------------------------------------------------------

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
	_HelpSection = 'video'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_AniDB,
			regexp = r'^anidb (?P<findme>.+)$',
			help = ('anidb', '\02anidb\02 <name> : Search for anime information on AniDB.'),
		)
		self.addTextEvent(
			method = self.__Fetch_AnimeNFO,
			regexp = r'^animenfo (?P<findme>.+)$',
			help = ('animenfo', '\02animenfo\02 <name> : Search for anime information on AnimeNFO.'),
		)
	
	# ---------------------------------------------------------------------------
	
	def __Fetch_AniDB(self, trigger):
		url = ANIDB_URL % QuoteURL(trigger.match.group('findme').lower())
		self.urlRequest(trigger, self.__Parse_AniDB, url)
	
	def __Fetch_AnimeNFO(self, trigger):
		async_animenfo(self, trigger)
	
	# ---------------------------------------------------------------------------
	# Parse an AniDB page
	def __Parse_AniDB(self, trigger, resp):
		findme = trigger.match.group('findme').lower()
		
		# If it's search results, parse them and spit them out
		if resp.data.find('Search for:') >= 0:
			# We need some results, damn you
			chunks = FindChunks(resp.data, '<a href="animedb.pl?show=anime&aid=', '</td>')
			if not chunks:
				replytext = 'No results found for "%s"' % findme
				self.sendReply(trigger, replytext)
				return
			
			# See if any of them are useful
			exact = None
			names = {}
			
			for chunk in chunks:
				# See if it's a "blah (see: blah)" link
				m = ANIDB_AKA_RE.search(chunk)
				if m:
					names[m.group(4)] = m.group(3)
					if m.group(2).lower() == findme:
						exact = (m.group(1), m.group(2))
					elif m.group(4).lower() == findme:
						exact = (m.group(3), m.group(4))
					continue
				
				m = ANIDB_RESULT_RE.search(chunk)
				if m:
					names[m.group(2)] = m.group(1)
					if m.group(2).lower() == findme:
						exact = m.groups()
					continue
			
			results = ['\x02[\x02%s\x02]\x02' % k for k in names.keys()]
			
			# Spit them out
			if len(results) == 0:
				replytext = 'Found no results, parse error?'
			if len(results) > 10:
				replytext = 'There were \002%s\002 results, first 10 :: %s' % (len(results), ' '.join(results[:10]))
			else:
				replytext = 'There were \002%s\002 result(s) :: %s' % (len(results), ' '.join(results))
			
			# If we found an exact match, go fetch it now
			if exact is not None:
				replytext += " :: Fetching '%s'" % (exact[1])
				
				url = AID_URL % exact[0]
				self.urlRequest(trigger, self.__Parse_AniDB, url)
			
			self.sendReply(trigger, replytext)
		
		# If it's an anime page, parse it and spit the info out
		elif resp.data.find('Show Anime - ') >= 0:
			parts = []
			
			# Find the info we want
			for thing in ('Title', 'Genre', 'Type', 'Episodes', 'Year', 'Producer', 'Rating'):
				chunk = FindChunk(resp.data, '%s:' % thing, '</tr>')
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
				
				# Eat stupid [graph] on the Rating field
				if thing == 'Rating' and info.endswith(' [graph]'):
					info = info[:-8]
				
				part = '\x02[\x02%s: %s\x02]\x02' % (thing, info)
				parts.append(part)
			
			# Find our aid
			m = re.search(r'name="aid" value="(\d+)"', resp.data)
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
		elif resp.data.find('Adult Content Warning') >= 0:
			self.sendReply(trigger, "Seems to be hentai, you need an AniDB user account to see the details :(")
		
		# Maintenance?
		elif resp.data.find('maintenance') >= 0:
			self.sendReply(trigger, "AniDB seems to be under maintenance. Again.")
		
		# Bad input
		elif resp.data.find('ILLEGAL INPUT') >= 0:
			self.sendReply(trigger, "AniDB says ILLEGAL INPUT. Naughty!")
		
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

class async_animenfo(buffered_dispatcher):
	def __init__(self, parent, trigger):
		buffered_dispatcher.__init__(self)
		
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
