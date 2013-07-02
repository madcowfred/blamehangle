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

IMDB_SEARCH_URL = 'http://www.imdb.com/find?s=tt&q=%s'
IMDB_TITLE_URL = 'http://www.imdb.com/title/tt%07d/'

IMDB_RESULT_RE = re.compile(r'<td class="result_text">\s*<a href="/title/tt(\d+)/.*?"\s*>\s*([^<>]+)</a>\s*\((\d+)[\)\/]')
IMDB_YEAR_RE = re.compile(r'>\(?(\d+[^\)<]*\d*)\s*\)?<')
# Maximum length of Plot: spam"
IMDB_MAX_PLOT = 180

YOUTUBE_REs = (
	re.compile('https?://(?:www\.)youtube\.com/.*?v=([^\&\#\s]+)'),
	re.compile('https?://youtu.be/([^\?\#\s]+)'),
)
YOUTUBE_URL = 'http://www.youtube.com/watch?v=%s'

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
			method = self.__Check_YouTube,
			regexp = r'^(.+)$',
			priority = -10,
			IRCTypes = (IRCT_PUBLIC,),
		)

	# ---------------------------------------------------------------------------

	def __Fetch_IMDb(self, trigger):
		findme = trigger.match.group(1)
		if findme.startswith('tt'):
			if findme[2:].isdigit():
				url = IMDB_TITLE_URL % (int(findme[2:]))
			else:
				url = IMDB_SEARCH_URL % QuoteURL(findme)
		else:
			url = IMDB_SEARCH_URL % QuoteURL(findme)
		self.urlRequest(trigger, self.__Parse_IMDb, url)

	# ---------------------------------------------------------------------------
	# Parse an IMDb search results page
	def __Parse_IMDb(self, trigger, resp):
		# If this isn't a search result, try it as a title.
		if '<title>Find -' not in resp.data:
			self.__IMDb_Title(trigger, resp)
			return

		findme = trigger.match.group(1)
		resp.data = UnquoteHTML(resp.data)

		parts = []

		# Find some chunks to look at
		chunks = [
			#FindChunk(resp.data, '<b>Popular Titles</b>', '</table>'),
			#FindChunk(resp.data, '<b>Titles (Exact Matches)</b>', '</table>'),
			#FindChunk(resp.data, '<b>Titles (Approx Matches)</b>', '</table>'),
			#FindChunk(resp.data, '<b>Titles (Partial Matches)</b>', '</table>'),
			FindChunk(resp.data, '<h3 class="findSectionHeader">', '</table>')
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
			chunk = FindChunk(resp.data, '<span class="itemprop" itemprop="name"', '</h1>')
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: h1/name.')
				return

			title_chunk = FindChunk(chunk, '>', '</span')
			if not title_chunk:
				self.sendReply(trigger, 'Page parsing failed: title.')
				return

			m = IMDB_YEAR_RE.search(chunk)
			if not m:
				self.sendReply(trigger, 'Page parsing failed: year.')
				return

			data['title'] = title_chunk.strip()
			data['year'] = m.group(1)

			# 'http://us.imdb.com/title/tt%07d/'
			data['url'] = resp.url[:len(IMDB_SEARCH_URL)+4]

			# Find the movie's genre(s)
			chunk = FindChunk(resp.data, 'Genres:</h4>', '</div>')
			if chunk:
				genres = FindChunks(chunk, '" >', '</a>')
				if not genres:
					self.sendReply(trigger, 'Page parsing failed: genres.')
					return

				data['genres'] = ', '.join(genres)

			# Find the plot
			chunk = FindChunk(resp.data, '<p itemprop="description">', '</p>')
			if chunk:
				chunk = chunk.strip()
				if len(chunk) > IMDB_MAX_PLOT:
					n = chunk.rfind(' ', 0, IMDB_MAX_PLOT)
					chunk = chunk[:n] + '...'

				data['plot'] = chunk

			# Find the rating
			chunk = FindChunk(resp.data, '<span itemprop="ratingValue">', '</span>')
			if chunk:
				#if 'awaiting 5 votes' not in chunk:
				#	rating = FindChunk(chunk, '<b>', '</b>')
				#	votes = FindChunk(chunk, '">', '</a>')
				#	if not rating or not votes:
				#		self.sendReply(trigger, 'Page parsing failed: rating.')
				#		return

				data['rating'] = chunk


			# Spit out the data
			parts = []
			for field in ('Title', 'Year', 'Genres', 'Rating', 'URL', 'Plot'):
				if data.get(field.lower(), None) is None:
					continue

				part = '\x02[\x02%s: %s\x02]\x02' % (field, data[field.lower()])
				parts.append(part)

			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)

	# ---------------------------------------------------------------------------

	def __Check_YouTube(self, trigger):
		text = trigger.match.group(1)
		for r in YOUTUBE_REs:
			m = r.search(text)
			if m:
				url = YOUTUBE_URL % (m.group(1))
				self.urlRequest(trigger, self.__Parse_YouTube, url)

	def __Parse_YouTube(self, trigger, resp):
		title = FindChunk(resp.data, '<title>', '</title>')
		title = title.replace('YouTube - ', '').replace(' - YouTube', '')
		replytext = 'YouTube: %s' % (title)
		self.sendReply(trigger, replytext, process=0)

# ---------------------------------------------------------------------------
