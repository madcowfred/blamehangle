# Copyright (c) 2003-2009, blamehangle team
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

'Look up information on movies/TV shows.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

IMDB_SEARCH_URL = 'http://us.imdb.com/find?s=tt&q=%s&x=0&y=0'
IMDB_TITLE_URL = 'http://us.imdb.com/title/tt%07d/'

IMDB_RESULT_RE = re.compile(r'/b.gif\?link=/title/tt(\d+)/\';">([^<>]+)</a> \((\d+)[\)\/]')
# Maximum length of Plot: spam
IMDB_MAX_PLOT = 150

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
		#self.addTextEvent(
		#	method = self.__Fetch_TVTome,
		#	regexp = r'^tvtome (.+)$',
		#	help = ('tvtome', '\02tvtome\02 <search term> : Search for a TV show  on TV Tome.'),
		#)
	
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
		if 'Search</title>' not in resp.data:
			self.__IMDb_Title(trigger, resp)
			return
		
		findme = trigger.match.group(1)
		resp.data = UnquoteHTML(resp.data)
		
		parts = []
		
		# Find some chunks to look at
		chunks = [
			FindChunk(resp.data, '<b>Popular Titles</b>', '</table>'),
			FindChunk(resp.data, '<b>Titles (Exact Matches)</b>', '</table>'),
			FindChunk(resp.data, '<b>Titles (Approx Matches)</b>', '</table>'),
			FindChunk(resp.data, '<b>Titles (Partial Matches)</b>', '</table>'),
		]
		
		# Find the titles
		results = []
		for chunk in chunks:
			if chunk is not None:
				results += IMDB_RESULT_RE.findall(chunk)
		
		# We found something!
		if results:
			parts = []
			for tt, title, year in results:
				if title.lower() == findme:
					url = IMDB_TITLE_URL % (int(tt))
					self.urlRequest(trigger, self.__IMDb_Title, url)
					return
				else:
					part = '\x02[\x02tt%s: %s (%s)\x02]\x02' % (tt, title, year)
					parts.append(part)
			
			# Spit it out
			if parts == []:
				replytext = 'Failed to parse page: no results!'
			else:
				replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
		
		# No we didn't :<
		else:
			replytext = 'Found no matches at all!'
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
			chunk = FindChunk(resp.data, 'Genre:</h5>', '</div>')
			if chunk:
				genres = FindChunks(chunk, '/">', '</a>')
				if not genres:
					self.sendReply(trigger, 'Page parsing failed: genre.')
					return
				
				data['genres'] = ', '.join(genres)
			
			# Find the plot
			chunk = FindChunk(resp.data, 'Plot:</h5>', '</div>')
			if chunk:
				chunk = chunk.strip()
				n = chunk.find(' | ')
				if n >= 0:
					chunk = chunk[:n]
				
				n = chunk.find(' <a')
				if n >= 0:
					chunk = chunk[:n]
				
				if len(chunk) > IMDB_MAX_PLOT:
					n = chunk.rfind(' ', 0, IMDB_MAX_PLOT)
					chunk = chunk[:n] + '...'
				
				data['plot'] = chunk
			
			# Find the rating
			chunk = FindChunk(resp.data, '<div class="meta">', '</div>')
			if chunk:
				if 'awaiting 5 votes' not in chunk:
					rating = FindChunk(chunk, '<b>', '</b>')
					votes = FindChunk(chunk, '">', '</a>')
					if not rating or not votes:
						self.sendReply(trigger, 'Page parsing failed: rating.')
						return
					
					data['rating'] = '%s - %s' % (rating, votes)
			
			
			# Spit out the data
			parts = []
			for field in ('Title', 'Year', 'Genres', 'Rating', 'URL', 'Plot'):
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
