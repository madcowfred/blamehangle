# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

import re
import time
import urllib
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

SELECT_QUERY = "SELECT url, description FROM torrents WHERE url IN (%s) OR description IN (%s)"
RECENT_QUERY = "SELECT added, url, description FROM torrents ORDER BY added DESC LIMIT 20"
INSERT_QUERY = "INSERT INTO torrents (added, url, description) VALUES (%s,%s,%s)"

# ARGH!
ENTITY_RE = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;)')

# ---------------------------------------------------------------------------

class TorrentScraper(Plugin):
	_QuietURLErrors = 1
	
	def setup(self):
		self.URLs = {}
		
		self.rehash()
	
	def rehash(self):
		# Easy way to get general options
		self.Options = self.SetupOptions('TorrentScraper')
		
		# Get the list of URLs from our config
		newurls = {}
		for option in self.Config.options('TorrentScraper-URLs'):
			newurls[self.Config.get('TorrentScraper-URLs', option)] = 0
		
		# Add any new ones to the list
		for url in newurls.keys():
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
		if self.Options['rss_path']:
			self.addTimedEvent(
				method = self.__Query_RSS,
				interval = self.Options['rss_interval'],
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
	
	def __Query_RSS(self, trigger):
		self.dbQuery(trigger, self.__Generate_RSS, RECENT_QUERY)
	
	# -----------------------------------------------------------------------
	# Do some page parsing!
	def __Parse_Page(self, trigger, resp):
		# If it hasn't been modified, we can continue on our merry way
		if resp.response == '304':
			return
		
		# Remember the Last-Modified header if it was sent
		self.URLs[resp.url]['last-modified'] = resp.headers.get('Last-Modified', None)
		
		items = {}
		
		# We don't want stupid HTML entities
		resp.data = UnquoteHTML(resp.data)
		
		# But we do want to quote the damn ampersands properly
		resp.data = ENTITY_RE.sub('&amp;', resp.data)
		
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
				newurl = newurl.replace('&amp;', '&')
				if newurl in items:
					continue
				
				# Keep it for a bit
				items[newurl] = (newurl, description)
		
		# Otherwise, go the easy way
 		else:
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
		ldescs = dict([(row['description'].lower(), None) for row in result])
		lurls = dict([(row['url'].lower(), None) for row in result])
		
		now = int(time.time())
		for item in items:
			# If we haven't seen this before, insert it
			if (item[0].lower() not in lurls) and (item[1].lower() not in ldescs):
				self.dbQuery(trigger, None, INSERT_QUERY, now, item[0], item[1])
	
	# -----------------------------------------------------------------------
	# Generate a simple RSS feed with our findings
	def __Generate_RSS(self, trigger, result):
		if result is None:
			self.putlog(LOG_WARNING, '__Generate_RSS: A DB error occurred!')
			return
		
		t1 = time.time()
		
		try:
			rssfile = open(self.Options['rss_path'], 'w')
		
		except Exception, msg:
			tolog = "Error opening %s for writing: %s" % (self.Options['rss_path'], msg)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# RSS header
		builddate = ISODate(time.time())
		
		print >>rssfile, """<?xml version="1.0" encoding="iso-8859-1"?>
<rss version="2.0">
<channel>
<title>TorrentScraper</title>
<link>http://www.nowhere.com</link>
<description>An RSS feed generated by TorrentScraper</description>
<language>en-us</language>
<lastBuildDate>%s</lastBuildDate>
<generator>blamehangle</generator>
<ttl>%s</ttl>""" % (builddate, self.Options['rss_interval'])
		
		# Items!
		for row in result:
			lines = []
			lines.append('<item>')
			lines.append('<title>%s</title>' % ENTITY_RE.sub('&amp;', row['description']))
			quotedurl = ENTITY_RE.sub('&amp;', urllib.quote(row['url'], ':/&'))
			lines.append('<guid>%s</guid>' % quotedurl)
			lines.append('<pubDate>%s</pubDate>' % ISODate(row['added']))
			lines.append('</item>')
			print >>rssfile, '\n'.join(lines)
		
		# RSS footer
		print >>rssfile, """</channel>
</rss>"""
		
		rssfile.close()
		
		tolog = "RSS feed generated in %.2fs" % (time.time() - t1)
		self.putlog(LOG_ALWAYS, tolog)

# ---------------------------------------------------------------------------
# Return an ISOblah date string
def ISODate(t):
	return time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.localtime(t))

# ---------------------------------------------------------------------------
