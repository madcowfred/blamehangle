# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Scrapes pages at a specific interval and keeps track of torrents on them,
then generates an RSS feed of the latest ones.
"""

import re
import time
import urllib
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

from classes.SimpleRSSGenerator import SimpleRSSGenerator

# ---------------------------------------------------------------------------

SELECT_QUERY = "SELECT url, description FROM torrents WHERE url IN (%s) OR description IN (%s)"
RECENT_QUERY = "SELECT added, url, description FROM torrents ORDER BY added DESC LIMIT 20"
INSERT_QUERY = "INSERT INTO torrents (added, url, description) VALUES (%s,%s,%s)"

# ---------------------------------------------------------------------------

class TorrentScraper(Plugin):
	_QuietURLErrors = 1
	_UsesDatabase = 'TorrentScraper'
	
	def setup(self):
		self.URLs = {}
		
		self.rehash()
	
	def rehash(self):
		# Easy way to get general options
		self.Options = self.OptionsDict('TorrentScraper')
		
		# Get the list of URLs from our config
		newurls = self.OptionsList('TorrentScraper-URLs')
		
		# Add any new ones to the list
		for url in newurls:
			if url not in self.URLs:
				self.URLs[url] = {
					'checked': 0,
					'last-modified': None,
				}
		
		# Remove any old ones
		for url in self.URLs.keys():
			if url not in newurls:
				del self.URLs[url]
	
	def register(self):
		self.addTimedEvent(
			method = self.__Scrape_Check,
			interval = self.Options['request_interval'],
		)
	
	# -----------------------------------------------------------------------
	# Get some URLs that haven't been checked recently
	def __Scrape_Check(self, trigger):
		now = time.time()
		
		ready = [(v['checked'], v, k) for k, v in self.URLs.items() if now - v['checked'] > self.Options['scrape_interval']]
		ready.sort()
		for checked, info, url in ready[:1]:
			info['checked'] = now
			
			# Maybe send an If-Modified-Since header
			if info['last-modified'] is not None:
				headers = {'If-Modified-Since': info['last-modified']}
				self.urlRequest(trigger, self.__Parse_Page, url, headers=headers)
			else:
				self.urlRequest(trigger, self.__Parse_Page, url)
	
	# -----------------------------------------------------------------------
	# Do some page parsing!
	def __Parse_Page(self, trigger, resp):
		# If it hasn't been modified, we can continue on our merry way
		if resp.response == '304':
			return
		
		# Remember the Last-Modified header if it was sent
		try:
			self.URLs[resp.url]['last-modified'] = resp.headers.get('last-modified', None)
		except KeyError:
			pass
		
		items = {}
		
		# We don't want stupid HTML entities
		resp.data = UnquoteHTML(resp.data)
		
		# If it's a BNBT page, we have to do some yucky searching
		if resp.data.find('BNBT') >= 0:
			# Find the URL bits we want
			chunks = FindChunks(resp.data, '<td class="name">', '</tr>')
			if not chunks:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
			
			# Yuck
			for chunk in chunks:
				# Get the bits we need
				description = FindChunk(chunk, '>', '<')
				href = FindChunk(chunk, 'class="download" href="', '"')
				if not description or not href:
					continue
				
				# Build the new URL
				newurl = UnquoteURL(urlparse.urljoin(resp.url, href))
				# Dirty filthy ampersands
				#newurl = newurl.replace('&amp;', '&')
				if newurl in items:
					continue
				
				# Keep it for a bit
				items[newurl] = (newurl, description)
		
		# Otherwise, go the easy way
 		else:
			# Find all of our URLs
			chunks = FindChunks(resp.data, '<a ', '</a>') + FindChunks(resp.data, '<A ', '</A>')
			if not chunks:
				open('/home/freddie/wtf.html', 'w').write(resp.data)
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
 			
			# See if any are talking about torrents
			for chunk in chunks:
				# Find the URL
				href = FindChunk(chunk, 'href="', '"') or \
					FindChunk(chunk, "href='", "'") or \
					FindChunk(chunk, 'HREF="', '"')
				
				if not href or href.find('.torrent') < 0:
					continue
				
 				# Build the new URL
				newurl = UnquoteURL(urlparse.urljoin(resp.url, href))
				# Dirty filthy ampersands
				newurl = newurl.replace('&amp;', '&')
 				if newurl in items:
 					continue
 				
 				# Get some text to describe it
				bits = chunk.split('>', 1)
				if len(bits) != 2:
					continue
 				
				lines = StripHTML(bits[1])
 				if len(lines) != 1:
 					continue
				
				# Keep it for a bit
				items[newurl] = (newurl, lines[0])
		
		# If we found nothing, bug out
		if items == {}:
			tolog = "Found no torrents at %s!" % resp.url
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Switch back to a list
		items = items.values()
		trigger.items = items
		
		# Build our query
		args = [item[0] for item in items] + [item[1] for item in items]
		querybit = ', '.join(['%s'] * len(items))
		query = SELECT_QUERY % (querybit, querybit)
		
		# And execute it
		self.dbQuery(trigger, self.__DB_Check, query, *args)
	
	# -----------------------------------------------------------------------
	# Handle the check reply
	def __DB_Check(self, trigger, result):
		# Error!
		if result is None:
			return
		
		items = trigger.items
		del trigger.items
		
		# This way is anywhere from 2 to 20 times faster than the old way.
		t1 = time.time()
		ldescs = dict([(row['description'].lower(), None) for row in result])
		lurls = dict([(row['url'].lower(), None) for row in result])
		
		t2 = time.time()
		ldescs2 = {}.fromkeys([row['description'] for row in result])
		lurls2 = {}.fromkeys([row['url'] for row in result])
		
		found = 0
		now = int(time.time())
		for item in items:
			# If we haven't seen this before, insert it
			if (item[0].lower() not in lurls) and (item[1].lower() not in ldescs):
				found = 1
				self.dbQuery(trigger, None, INSERT_QUERY, now, item[0], item[1])
		
		# If we found some new ones, generate the RSS feed now
		if found:
			self.dbQuery(trigger, self.__Generate_RSS, RECENT_QUERY)
	
	# -----------------------------------------------------------------------
	# Generate a simple RSS feed with our findings
	def __Generate_RSS(self, trigger, result):
		if result is None:
			self.putlog(LOG_WARNING, '__Generate_RSS: A DB error occurred!')
			return
		
		# Make up some feed info
		feedinfo = {
			'title': self.Options.get('rss_title', 'TorrentScraper'),
			'link': self.Options.get('rss_title', 'http://www.example.com'),
			'description': self.Options.get('rss_title', 'An automatically generated RSS feed from scraped torrent pages'),
			'ttl': 300,
		}
		
		# Make up our items
		items = []
		for row in result:
			items.append({
				'title': row['description'],
				'link': row['url'],
				'pubdate': time.gmtime(row['added']),
			})
		
		# And generate it
		SimpleRSSGenerator(self.Options['rss_path'], feedinfo, items, self.putlog)

# ---------------------------------------------------------------------------
