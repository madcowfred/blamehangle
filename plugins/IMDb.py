# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Interface to IMDb, for moderately lazy people

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

IMDB_IMDB = 'IMDB_IMDB'
IMDB_RE = re.compile(r'^imdb (.+)$')
IMDB_HELP = '\02imdb\02 <search term> : Search for a movie on IMDb.'
IMDB_URL = "http://us.imdb.com/find?q=%s&type=fuzzy&tv=off&sort=smart;tt=1"

IMDB_TITLE = 'IMDB_TITLE'
TITLE_RE = re.compile(r'^imdbtitle (\d{1,7})$')
TITLE_HELP = '\02imdb\02 <number> : Show information on a specific title number on IMDb.'
TITLE_URL = "http://us.imdb.com/title/tt%07d/"

EXACT_RE = re.compile(r'href="/title/tt(\d+)/">')
APPROX_RE = re.compile(r'href="/title/tt(\d+)/">(.+)')

# ---------------------------------------------------------------------------

class IMDb(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		imdb_dir = PluginTextEvent(IMDB_IMDB, IRCT_PUBLIC_D, IMDB_RE)
		imdb_msg = PluginTextEvent(IMDB_IMDB, IRCT_MSG, IMDB_RE)
		title_dir = PluginTextEvent(IMDB_TITLE, IRCT_PUBLIC_D, TITLE_RE)
		title_msg = PluginTextEvent(IMDB_TITLE, IRCT_MSG, TITLE_RE)
		self.register(imdb_dir, imdb_msg, title_dir, title_msg)
		
		self.setHelp('imdb', 'imdb', IMDB_HELP)
		self.setHelp('imdb', 'imdbtitle', TITLE_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == IMDB_IMDB:
			url = IMDB_URL % QuoteURL(trigger.match.group(1))
			self.urlRequest(trigger, url)
		
		elif trigger.name == IMDB_TITLE:
			url = TITLE_URL % int(trigger.match.group(1))
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == IMDB_IMDB:
			self.__IMDb(trigger, page_text)
		
		elif trigger.name == IMDB_TITLE:
			self.__Title(trigger, page_text)
	
	# ---------------------------------------------------------------------------
	
	def __IMDb(self, trigger, page_text):
		# If this isn't a search result, try it as a title.
		if page_text.find('title search</title>') < 0:
			self.__Title(trigger, page_text)
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
			
			trigger.name = IMDB_TITLE
			
			title = m.group(1)
			url = TITLE_URL % int(title)
			self.urlRequest(trigger, url)
		
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
	
	def __Title(self, trigger, page_text):
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
			
			# Find the plot outline
			chunk = FindChunk(page_text, 'Plot Outline:</b>', '<br>')
			if chunk:
				n = chunk.find('<a')
				if n >= 0:
					chunk = chunk[:n]
				data['outline'] = chunk.strip()
			
			# Find the rating
			chunk = FindChunk(page_text, 'goldstar.gif', '<a')
			if chunk:# is None:
				#self.sendReply(trigger, 'Page parsing failed: rating.')
				#return
				
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
				
				part = '\02[\02%s\02]\02 %s' % (field, data[field.lower()])
				parts.append(part)
			
			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
			
			print 'replytext:', replytext
