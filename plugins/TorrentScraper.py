# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004, MadCowDisease
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#	 this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#	 this list of conditions, and the following disclaimer in the
#	 documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#	 contributors to this software may be used to endorse or promote products
#	 derived from this software without specific prior written consent.
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

"""
Scrapes pages at a specific interval and keeps track of torrents on them,
then generates an RSS feed of the latest ones.
"""

import time
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin
from classes.SimpleCacheDict import SimpleCacheDict

from classes.SimpleRSSGenerator import SimpleRSSGenerator
from classes.SimpleRSSParser import SimpleRSSParser

# ---------------------------------------------------------------------------

SELECT_URL_QUERY = "SELECT url FROM torrents WHERE url IN (%s)"
SELECT_FILENAME_QUERY = "SELECT filename FROM torrents WHERE filename = %s"
INSERT_QUERY = "INSERT INTO torrents (scrape_time, url, filename, filesize) VALUES (%s, %s, %s, %s)"
RECENT_QUERY = "SELECT scrape_time, url, filename, filesize FROM torrents WHERE filename != '' ORDER BY scrape_time DESC LIMIT 20"

# ---------------------------------------------------------------------------

class TorrentScraper(Plugin):
	_QuietURLErrors = 1
	_UsesDatabase = 'TorrentScraper'
	
	def setup(self):
		self._Broken = SimpleCacheDict(1)
		self._FetchMe = []
		self._Pages = {}
		self._RSS_Generated = 0
		
		self.rehash()
	
	def rehash(self):
		# Easy way to get general options
		self.Options = self.OptionsDict('TorrentScraper')
		
		# Update our cache length and expire
		self._Broken.cachesecs = self.Options['backoff_delay']
		self._Broken.expire()
		
		# Add any new pages
		currtime = time.time()
		sections = [s for s in self.Config.sections() if s.startswith('TorrentScraper.')]
		for section in sections:
			pageopts = self.OptionsDict(section)
			name = section.split('.', 1)[1]
			
			page = {
				'url': pageopts['url'],
				'style': pageopts.get('style', self.Options['default_style']),
				'interval': pageopts.get('interval', self.Options['default_interval']),
				'checked': currtime,
				'last-modified': None,
			}
			
			# If the page is new, just add it to the list
			if name not in self._Pages:
				self._Pages[name] = page
			# It's already there, just update the bits we need to update
			else:
				for k in page.keys():
					if k not in ('checked', 'last-modified'):
						self._Pages[name][k] = page[k]
		
		# And remove any that are no longer around
		for name in self._Pages.keys():
			section = 'TorrentScraper.%s' % name
			if section not in sections:
				del self._Pages[name]
	
	def register(self):
		self.addTimedEvent(
			method = self.__Scrape_Check,
			interval = self.Options['request_interval'],
		)
		if self.Options['rss_interval'] > 0:
			self.addTimedEvent(
				method = self.__Generate_RSS,
				interval = self.Options['rss_interval'],
			)
	
	# -----------------------------------------------------------------------
	# Get some URLs that haven't been checked recently
	def __Scrape_Check(self, trigger):
		# Work out which page was checked least recently
		currtime = time.time()
		ready = []
		for name, page in self._Pages.items():
			if (currtime - page['checked']) >= page['interval']:
				ready.append((page['interval'], name, page))
		ready.sort()
		
		# Fetch it
		for checked, name, page in ready[:1]:
			trigger.source = name
			page['checked'] = currtime
			
			# Maybe send an If-Modified-Since header
			if page['last-modified'] is not None:
				headers = {'If-Modified-Since': page['last-modified']}
				self.urlRequest(trigger, self.__Parse_Page, page['url'], headers=headers)
			else:
				self.urlRequest(trigger, self.__Parse_Page, page['url'])
		
		# Maybe check a torrent too
		self.__Fetch_Next_Torrent(trigger)
	
	# -----------------------------------------------------------------------
	# Do some page parsing!
	def __Parse_Page(self, trigger, resp):
		# If it hasn't been modified, we can continue on our merry way
		if resp.response == '304':
			return
		
		# Remember the Last-Modified header if it was sent
		self._Pages[trigger.source]['last-modified'] = resp.headers.get('last-modified', None)
		
		# We don't want stupid HTML entities
		resp.data = UnquoteHTML(resp.data)
		
		# See what sort of parsing we get to do
		torrents = {}
		page = self._Pages[trigger.source]
		
		# Normal HTML links
		if page['style'] == 'links':
			# Find all of our URLs
			chunks = FindChunks(resp.data, '<a ', '</a>') + FindChunks(resp.data, '<A ', '</A>')
			if not chunks:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
 			
			# See if any are talking about torrents
			for chunk in chunks:
				# Find the URL
				href = FindChunk(chunk, 'href="', '"') or \
					FindChunk(chunk, "href='", "'") or \
					FindChunk(chunk, 'HREF="', '"')
				
				if href is None or '.torrent' not in href:
					continue
				
 				# Build the new URL
				newurl = UnquoteURL(urlparse.urljoin(resp.url, href)).replace('%20', ' ')
				newurl = newurl.replace('&amp;', '&')
 				
				# Keep it for a bit
				torrents[newurl] = True
		
		# BNBT page, grr
		elif page['style'] == 'bnbt':
			# Find the URL bits we want
			chunks = FindChunks(resp.data, '<a class="download" href="', '"')
			if not chunks:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
			
			# Build our new URLs
			for chunk in chunks:
				newurl = UnquoteURL(urlparse.urljoin(resp.url, chunk)).replace('%20', ' ')
				
				torrents[newurl] = True
		
		# Stupid "torrent trader lite"
		elif page['style'] == 'ttl':
			# Find all of our URLs
			urls = FindChunks(resp.data, '<a href="download.php?', '"')
			if not urls:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
 			
 			# Fix 'em
 			for url in urls:
 				newurl = 'download.php?%s' % (url)
				newurl = UnquoteURL(urlparse.urljoin(resp.url, newurl)).replace('%20', ' ')
				newurl = newurl.replace('&amp;', '&')
				
				torrents[newurl] = True
		
		# RSS feed
		elif page['style'] == 'rss':
			try:
				rss = SimpleRSSParser(resp.data)
			except Exception, msg:
				tolog = "Error parsing RSS feed '%s': %s" % (trigger.source, msg)
				self.putlog(LOG_WARNING, tolog)
				return
			
			# Grab the torrents
			for item in rss['items']:
				if 'enclosure' in item:
					newurl = UnquoteURL(item['enclosure']['url']).replace('%20', ' ')
				else:
					newurl = UnquoteURL(item['link']).replace('%20', ' ')
				
				torrents[newurl] = True
		
		
		# If we found nothing, bug out
		if torrents == {}:
			tolog = 'Found no torrents at %s!' % (resp.url)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Build our query
		args = torrents.keys()
		querybit = ', '.join(['%s'] * len(args))
		query = SELECT_URL_QUERY % (querybit)
		
		# And execute it
		trigger.torrents = args
		self.dbQuery(trigger, self.__DB_Check_URL, query, *args)
	
	# -----------------------------------------------------------------------
	# Handle the DB reply for URL lookup
	def __DB_Check_URL(self, trigger, result):
		# Error!
		if result is None:
			return
		
		torrents = trigger.torrents
		del trigger.torrents
		
		# See which ones are new
		urls = {}.fromkeys([row['url'] for row in result], True)
		torrents = [t for t in torrents if t not in urls and t not in self._FetchMe]
		
		# If we have some, add them to the fetch list
		if torrents:
			self._FetchMe.extend(torrents)
	
	# -----------------------------------------------------------------------
	# Fetch the next torrent
	def __Fetch_Next_Torrent(self, trigger):
		while self._FetchMe:
			url = QuoteURL(self._FetchMe.pop(0))
			# Don't try it if it's still marked broken
			if url in self._Broken:
				tolog = '"%s" is marked as broken, skipping!'
				self.putlog(LOG_DEBUG, tolog)
				continue
			
			trigger.origurl = url
			self.urlRequest(trigger, self.__Parse_Torrent, url)
	
	# Parse torrent metadata or something
	def __Parse_Torrent(self, trigger, resp):
		# Grab the filename from the torrent metadata
		try:
			metainfo = bdecode(resp.data)['info']
		except ValueError:
			tolog = '"%s" is not a valid torrent!' % (resp.url)
			self.putlog(LOG_DEBUG, tolog)
			# Mark it as borken
			self._Broken[trigger.origurl] = True
		else:
			filename = metainfo['name']
			# If there's more than one file, sum up the sizes
			if 'files' in metainfo:
				filesize = sum([f['length'] for f in metainfo['files']])
			else:
				filesize = metainfo['length']
			
			# See if it's already in the DB
			trigger.temp = (resp, filename, filesize)
			self.dbQuery(trigger, self.__DB_Check_Filename, SELECT_FILENAME_QUERY, filename)
	
	# Handle the DB reply for filename lookup
	def __DB_Check_Filename(self, trigger, result):
		resp, filename, filesize = trigger.temp
		del trigger.temp
		
		if result is None:
			return
		
		# If the filename is already there, insert with a blank filename so we
		# don't keep trying it over and over.
		now = int(time.time())
		url = UnquoteURL(trigger.origurl).replace('%20', ' ')
		if result:
			args = [now, url, '', 0]
		else:
			args = [now, url, filename, filesize]
		
		self.dbQuery(trigger, None, INSERT_QUERY, *args)
	
	# -----------------------------------------------------------------------
	# Generate a simple RSS feed with our findings
	def __Generate_RSS(self, trigger):
		self.dbQuery(trigger, self.__DB_Recent, RECENT_QUERY)
	
	def __DB_Recent(self, trigger, result):
		if result is None:
			self.putlog(LOG_WARNING, '__DB_Recent: A DB error occurred!')
			return
		
		# If there's nothing new, don't generate it
		if result[0]['scrape_time'] < self._RSS_Generated:
			return
		self._RSS_Generated = time.time()
		
		# Make up some feed info
		feedinfo = {
			'title': self.Options.get('rss_title', 'TorrentScraper'),
			'link': self.Options.get('rss_link', 'http://www.example.com'),
			'description': self.Options.get('rss_description', 'An automatically generated RSS feed from scraped torrent pages'),
			'ttl': self.Options['rss_interval'],
		}
		
		# Make up our items
		items = []
		for row in result:
			items.append({
				'title': '%s (%.1fMB)' % (row['filename'], row['filesize'] / 1024.0 / 1024.0),
				'link': row['url'],
				'pubdate': time.gmtime(row['scrape_time']),
			})
		
		# And generate it
		SimpleRSSGenerator(self.Options['rss_path'], feedinfo, items, self.putlog)

# ---------------------------------------------------------------------------
# Copied from BitTorrent/bencode.py!
def decode_int(x, f):
	f += 1
	newf = x.index('e', f)
	n = int(x[f:newf])
	if x[f] == '-':
		if x[f + 1] == '0':
			raise ValueError
	elif x[f] == '0' and newf != f+1:
		raise ValueError
	return (n, newf+1)

def decode_string(x, f):
	colon = x.index(':', f)
	n = int(x[f:colon])
	if x[f] == '0' and colon != f+1:
		raise ValueError
	colon += 1
	return (x[colon:colon+n], colon+n)

def decode_list(x, f):
	r, f = [], f+1
	while x[f] != 'e':
		v, f = decode_func[x[f]](x, f)
		r.append(v)
	return (r, f + 1)

def decode_dict(x, f):
	r, f = {}, f+1
	lastkey = None
	while x[f] != 'e':
		k, f = decode_string(x, f)
		if lastkey >= k:
			raise ValueError
		lastkey = k
		r[k], f = decode_func[x[f]](x, f)
	return (r, f + 1)

decode_func = {}
decode_func['l'] = decode_list
decode_func['d'] = decode_dict
decode_func['i'] = decode_int
decode_func['0'] = decode_string
decode_func['1'] = decode_string
decode_func['2'] = decode_string
decode_func['3'] = decode_string
decode_func['4'] = decode_string
decode_func['5'] = decode_string
decode_func['6'] = decode_string
decode_func['7'] = decode_string
decode_func['8'] = decode_string
decode_func['9'] = decode_string

def bdecode(x):
	try:
		r, l = decode_func[x[0]](x, 0)
	except (IndexError, KeyError, ValueError):
		raise ValueError, 'not a valid bencoded string'
	if l != len(x):
		raise ValueError, 'invalid bencoded value (data after valid prefix)'
	return r

# ---------------------------------------------------------------------------
