# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Look up information on movies/TV shows.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

IMDB_SEARCH_URL = 'http://us.imdb.com/find?q=%s;tt=on;mx=10'
IMDB_TITLE_URL = 'http://us.imdb.com/title/tt%07d/'

IMDB_RESULT_RE = re.compile(r'href="/title/tt(\d+)/[^>]+">(.*?)</a> \((\d+)\)')

# ---------------------------------------------------------------------------

TVTOME_URL = 'http://www.tvtome.com/tvtome/servlet/Search'

# ---------------------------------------------------------------------------

class Video(Plugin):
	_HelpSection = 'video'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_IMDb,
			regexp = r'^imdb (?P<findme>.+)$',
			help = ('imdb', "\02imdb\02 <search term> : Search for a movie on IMDb. Use 'tt1234567' for a specific title."),
		)
		self.addTextEvent(
			method = self.__Fetch_TVTome,
			regexp = r'^tvtome (.+)$',
			help = ('tvtome', '\02tvtome\02 <search term> : Search for a TV show  on TV Tome.'),
		)
	
	# ---------------------------------------------------------------------------
	
	def __Fetch_IMDb(self, trigger):
		findme = trigger.match.group(1)
		url = IMDB_SEARCH_URL % QuoteURL(findme)
		self.urlRequest(trigger, self.__Parse_IMDb, url)
	
	def __Fetch_TVTome(self, trigger):
		data = {
			'searchType': 'show',
			'searchString': trigger.match.group(1).lower(),
		}
		
		self.urlRequest(trigger, self.__Parse_TVTome, TVTOME_URL, data)
	
	# ---------------------------------------------------------------------------
	# Parse an IMDb search results page
	def __Parse_IMDb(self, trigger, resp):
		# If this isn't a search result, try it as a title.
		if resp.data.find('IMDb title search') < 0:
			self.__IMDb_Title(trigger, resp)
			return
		
		findme = trigger.match.group(1)
		resp.data = UnquoteHTML(resp.data)
		
		# We only care about Popular Titles for now
		if resp.data.find('<b>Popular Titles</b>') >= 0:
			# Get the chunk with the titles inside
			chunk = FindChunk(resp.data, '<b>Popular Titles</b>', '</p>')
			if chunk is None:
				replytext = 'Failed to parse page: no Popular Titles?'
				self.sendReply(trigger, replytext)
				return
			
			# Find the titles
			lis = FindChunks(chunk, '<li>', '</li>')
			if lis == []:
				replytext = 'Failed to parse page: no Popular Titles items?'
				self.sendReply(trigger, replytext)
				return
			
			# Get the info we need
			parts = []
			
			for li in lis[:5]:
				m = IMDB_RESULT_RE.search(li)
				if not m:
					continue
				
				# We probably found what we were after
				if m.group(2).lower() == findme:
					url = IMDB_TITLE_URL % (int(m.group(1)))
					self.urlRequest(trigger, self.__IMDb_Title, url)
					return
				
				part = '\x02[\x02tt%s: %s (%s)\x02]\x02' % m.groups()
				parts.append(part)
			
			# Spit it out
			if parts == []:
				replytext = 'Failed to parse page: no matching Popular Titles?'
			else:
				replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
		
		# FIXME: spit out some alternate matches
		else:
			replytext = 'Found no matches at all, you suck.'
			self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	
	def __IMDb_Title(self, trigger, resp):
		resp.data = UnquoteHTML(resp.data)
		
		# No match, arg!
		if resp.data.find('Page not found') >= 0:
			self.sendReply(trigger, 'Title not found!')
		
		# We have a winner
		else:
			data = {}
			
			# Find the movie's title and year
			m = re.search(r'<title>(.+) \((\d+).*?\)</title>', resp.data)
			if not m:
				self.sendReply(trigger, 'Page parsing failed: title.')
				return
			
			data['title'] = m.group(1)
			data['year'] = m.group(2)
			
			# 'http://us.imdb.com/title/tt%07d/'
			data['url'] = resp.url[:len(IMDB_SEARCH_URL)+4]
			
			# Find the movie's genre(s)
			chunk = FindChunk(resp.data, 'Genre:</b>', '<br>')
			if chunk:
				genres = FindChunks(chunk, '/">', '</a>')
				if not genres:
					self.sendReply(trigger, 'Page parsing failed: genre.')
					return
				
				data['genres'] = ', '.join(genres)
			
			# Find the plot outline, or maybe it's a summary today
			chunk = FindChunk(resp.data, 'Plot Outline:</b>', '<br>')
			if not chunk:
				chunk = FindChunk(resp.data, 'Plot Summary:</b>', '<br>')
			
			if chunk:
				n = chunk.find('<a')
				if n >= 0:
					chunk = chunk[:n]
				data['outline'] = chunk.strip()
			
			# Find the rating
			chunk = FindChunk(resp.data, 'goldstar.gif', '<a')
			if chunk:
				m = re.search(r'<b>(.+)</b> (\(.+ votes\))', chunk)
				if not m:
					self.sendReply(trigger, 'Page parsing failed: rating.')
					return
				
				data['rating'] = '%s %s' % m.groups()
			
			
			# Spit out the data
			parts = []
			for field in ('Title', 'Year', 'Genres', 'Rating', 'URL', 'Outline'):
				if data.get(field.lower(), None) is None:
					continue
				
				part = '\02[\02%s: %s\02]\02' % (field, data[field.lower()])
				parts.append(part)
			
			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	# Parse a TVTome search results page
	def __Parse_TVTome(self, trigger, resp):
		findme = trigger.match.group(1).lower()
		
		# It's not a search result
		if resp.data.find('Show search for:') < 0:
			self.__TVTome_Show(trigger, resp)
		
		# It is a search result!
		else:
			# Find the results block
			chunk = FindChunk(resp.data, 'Show search for:', "Didn't find what you")
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: results.')
				return
			
			# Find the shows
			shows = FindChunks(chunk, '<a href="', '</a>')
			if shows:
				exact = None
				parts = []
				
				for show in shows:
					try:
						path, show = show.split('">')
					except ValueError:
						continue
					
					part = '\02[\02%s\02]\02' % (show)
					parts.append(part)
					
					if show.lower() == findme:
						exact = (path, show)
				
				if len(parts) > 10:
					replytext = 'Found \02%d\02 results, first 10: %s' % (len(parts), ' '.join(parts[:10]))
				else:
					replytext = 'Found \02%d\02 results: %s' % (len(parts), ' '.join(parts))
				
				# If we found an exact match, go fetch it now
				if exact is not None:
					replytext += " :: Using '%s'" % (exact[1])
					
					url = 'http://www.tvtome.com' + exact[0]
					self.urlRequest(trigger, self.__TVTome_Show, url)
			
			else:
				replytext = 'No results found.'
			
			self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	# Parse a TVTome show info page
	def __TVTome_Show(self, trigger, resp):
		# Find the show title
		show_title = FindChunk(resp.data, '<h1>', '</h1>')
		if not show_title:
			self.sendReply(trigger, 'Page parsing failed: show title.')
			return
		
		# Find the show info
		chunk = FindChunk(resp.data, '<!-- Show Information body Begins -->', '<!-- Show Information body Ends -->')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: show info.')
			return
		
		chunk = FindChunk(chunk, '<table width="575"', '</table>')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: show info table.')
			return
		
		# Find the table cells!
		data = [('Title', show_title)]
		
		trs = FindChunks(chunk, '<tr>', '</tr>')
		for tr in trs:
			tds = FindChunks(tr, '">', '</td>')
			if len(tds) == 2:
				data.append(tds)
		
		# Find the page URL
		path = FindChunk(resp.data, '<input type="hidden" name="returnTo" value="', '">')
		if path:
			url = 'http://www.tvtome.com' + path
			data.append(('URL', url))
		
		# We found stuff!
		if len(data) > 1:
			parts = []
			for k, v in data:
				part = '\02[\02%s: %s\02]\02' % (k, v)
				parts.append(part)
			replytext = ' '.join(parts)
		
		else:
			replytext = 'Page parsing failed: show info table cells.'
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
