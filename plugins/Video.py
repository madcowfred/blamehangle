# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Look up information on movies/TV shows.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

VIDEO_IMDB = 'VIDEO_IMDB'
IMDB_HELP = "\02imdb\02 <search term> : Search for a movie on IMDb. Use 'tt1234567' for a title."
IMDB_RE = re.compile(r'^imdb (.+)$')
IMDB_URL = 'http://us.imdb.com/find?q=%s&type=fuzzy&tv=off&sort=smart;tt=1'
TITLE_URL = 'http://us.imdb.com/title/tt%07d/'

EXACT_RE = re.compile(r'href="/title/tt(\d+)/">')
APPROX_RE = re.compile(r'href="/title/tt(\d+)/">(.+)')

# ---------------------------------------------------------------------------

VIDEO_TVTOME = 'VIDEO_TVTOME'
TVTOME_HELP = '\02tvtome\02 <search term> : Search for a TV show  on TV Tome.'
TVTOME_RE = re.compile(r'^tvtome (.+)$')
TVTOME_URL = 'http://www.tvtome.com/tvtome/servlet/Search'

# ---------------------------------------------------------------------------

class Video(Plugin):
	def register(self):
		self.setTextEvent(VIDEO_IMDB, IMDB_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(VIDEO_TVTOME, TVTOME_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('video', 'imdb', IMDB_HELP)
		self.setHelp('video', 'tvtome', TVTOME_HELP)
		self.registerHelp()
	
	# ---------------------------------------------------------------------------
	
	def _trigger_VIDEO_IMDB(self, trigger):
		url = IMDB_URL % QuoteURL(trigger.match.group(1))
		self.urlRequest(trigger, self.__IMDb, url)
	
	def _trigger_VIDEO_TVTOME(self, trigger):
		data = {
			'searchType': 'show',
			'searchString': trigger.match.group(1).lower(),
		}
		
		self.urlRequest(trigger, self.__TVTome, TVTOME_URL, data)
	
	# ---------------------------------------------------------------------------
	
	def __IMDb(self, trigger, page_url, page_text):
		# If this isn't a search result, try it as a title.
		if page_text.find('title search</title>') < 0:
			self.__IMDb_Title(trigger, page_text)
			return
		
		movie = trigger.match.group(1)
		page_text = UnquoteHTML(page_text)
		
		# Woo, some exact matches. Assume the first one is correct.
		if page_text.find('<b>Exact Matches</b>') >= 0:
			# Get the chunk with the titles inside
			chunk = FindChunk(page_text, '<b>Exact Matches</b>', '</table>')
			if chunk is None:
				replytext = 'Failed to parse page: no Exact Matches?'
				self.sendReply(trigger, replytext)
				return
			
			# Find the first title
			title_chunk = FindChunk(chunk, '<a', '</a>')
			if title_chunk is None:
				replytext = 'Failed to parse page: no Exact Matches?'
				self.sendReply(trigger, replytext)
				return
			
			# Go fetch it?
			m = EXACT_RE.search(title_chunk)
			if not m:
				replytext = 'Failed to parse page: no title number?'
				self.sendReply(trigger, replytext)
				return
			
			title = m.group(1)
			url = TITLE_URL % int(title)
			self.urlRequest(trigger, self.__IMDb_Title, url)
		
		# Some approximate matches.. use the first 5 results
		elif page_text.find('<b>Approximate Matches</b>') >= 0:
			# Get the chunk with the titles inside
			chunk = FindChunk(page_text, '<b>Approximate Matches</b>', '</table>')
			if chunk is None:
				replytext = 'Failed to parse page: no Approximate Matches?'
				self.sendReply(trigger, replytext)
				return
			
			# Find the titles
			titles = FindChunks(chunk, '<a', '</a>')
			if titles == []:
				replytext = 'Failed to parse page: no Approximate Matches?'
				self.sendReply(trigger, replytext)
				return
			
			# Get the info we need
			parts = []
			
			for title in titles[:5]:
				m = APPROX_RE.search(title)
				if not m:
					continue
				
				part = '%s: %s' % (m.group(2), m.group(1))
				parts.append(part)
			
			# Spit it out
			replytext = ' - '.join(parts)
			self.sendReply(trigger, replytext)
		
		# FIXME: spit out some alternate matches
		else:
			replytext = 'Found no matches at all, you suck.'
			self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	
	def __IMDb_Title(self, trigger, page_url, page_text):
		page_text = UnquoteHTML(page_text)
		
		# No match, arg!
		if page_text.find('Page not found') >= 0:
			self.sendReply(trigger, 'Title not found!')
		
		# We have a winner
		else:
			data = {}
			
			# Find the movie's title and year
			m = re.search(r'<title>(.+) \((\d+).*?\)</title>', page_text)
			if not m:
				self.sendReply(trigger, 'Page parsing failed: title.')
				return
			
			data['title'] = m.group(1)
			data['year'] = m.group(2)
			
			# Find the movie's number for a URL
			m = re.search(r'"/title/tt(\d+)/"', page_text)
			if not m:
				self.sendReply(trigger, 'Page parsing failed: number.')
				return
			
			data['url'] = 'http://us.imdb.com:80/title/tt%s' % m.group(1)
			
			# Find the movie's genre(s)
			chunk = FindChunk(page_text, 'Genre:</b>', '<br>')
			if chunk:
				genres = FindChunks(chunk, '/">', '</a>')
				if not genres:
					self.sendReply(trigger, 'Page parsing failed: genre.')
					return
				
				data['genres'] = ', '.join(genres)
			
			# Find the plot outline, or maybe it's a summary today
			chunk = FindChunk(page_text, 'Plot Outline:</b>', '<br>')
			if not chunk:
				chunk = FindChunk(page_text, 'Plot Summary:</b>', '<br>')
			
			if chunk:
				n = chunk.find('<a')
				if n >= 0:
					chunk = chunk[:n]
				data['outline'] = chunk.strip()
			
			# Find the rating
			chunk = FindChunk(page_text, 'goldstar.gif', '<a')
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
	def __TVTome(self, trigger, page_url, page_text):
		findme = trigger.match.group(1).lower()
		
		# It's not a search result
		if page_text.find('Show search for:') < 0:
			self.__TVTome_Show(trigger, page_text)
		
		# It is a search result!
		else:
			# Find the results block
			chunk = FindChunk(page_text, 'Show search for:', "Didn't find what you")
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
	def __TVTome_Show(self, trigger, page_url, page_text):
		# Find the show title
		show_title = FindChunk(page_text, '<h1>', '</h1>')
		if not show_title:
			self.sendReply(trigger, 'Page parsing failed: show title.')
			return
		
		# Find the show info
		chunk = FindChunk(page_text, '<!-- Show Information body Begins -->', '<!-- Show Information body Ends -->')
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
		path = FindChunk(page_text, '<input type="hidden" name="returnTo" value="', '">')
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
