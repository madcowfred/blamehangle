# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

import re
import time
import urllib
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

from classes.BeautifulSoup import BeautifulSoup

# ---------------------------------------------------------------------------

SCRAPE_TIMER = 'SCRAPE_TIMER'
RSS_TIMER = 'RSS_TIMER'

SELECT_QUERY = "SELECT url, description FROM torrents WHERE url IN (%s) OR description IN (%s)"
RECENT_QUERY = "SELECT added, url, description FROM torrents ORDER BY added DESC LIMIT 20"
INSERT_QUERY = "INSERT INTO torrents (added, url, description) VALUES (%s,%s,%s)"

# ARGH!
ENTITY_RE = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;)')

# ---------------------------------------------------------------------------

class TorrentScraper(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		# Easy way to get general options
		self.SetupOptions('TorrentScraper')
		
		# Now get our URLs
		self.URLs = {}
		for option in self.Config.options('TorrentScraper-URLs'):
			self.URLs[self.Config.get('TorrentScraper-URLs', option)] = 0
	
	def register(self):
		self.setTimedEvent(SCRAPE_TIMER, int(self.Options['request_interval']), None)
		if self.Options['rss_path']:
			self.setTimedEvent(RSS_TIMER, int(self.Options['rss_interval']) * 60, None)
			#self.setTimedEvent(RSS_TIMER, 10, None)
		
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# Get some URLs that haven't been checked recently
	def _trigger_SCRAPE_TIMER(self, trigger):
		interval = int(self.Options['scrape_interval']) * 60
		now = time.time()
		
		ready = [k for k, v in self.URLs.items() if now - v > interval]
		if ready:
			self.URLs[ready[0]] = now
			self.urlRequest(trigger, self.__Parse_Page, ready[0])
	
	def _trigger_RSS_TIMER(self, trigger):
		self.dbQuery(trigger, self.__Generate_RSS, RECENT_QUERY)
	
	# -----------------------------------------------------------------------
	# Do some page parsing!
	def __Parse_Page(self, trigger, resp):
		t1 = time.time()
		
		items = {}
		now = int(time.time())
		
		# We don't want stupid HTML entities
		resp.data = UnquoteHTML(resp.data)
		
		t2 = time.time()
		
		# But we do want to quote the damn ampersands properly
		resp.data = ENTITY_RE.sub('&amp;', resp.data)
		
		t3 = time.time()
		
		# If it's a BNBT page, we have to do some yucky searching
		if resp.data.find('POWERED BY BNBT') >= 0:
			# Find the URL bits we want
			chunks = FindChunks(resp.data, '<td class="name">', 'DL')
			if not chunks:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
			
			t4
			
			# Yuck
			for chunk in chunks:
				# Get the bits we need
				description = FindChunk(chunk, '>', '<')
				href = FindChunk(chunk, 'class="download" href="', '"')
				if not description or not href:
					continue
				
				# Build the new URL
				newurl = UnquoteURL(urlparse.urljoin(resp.url, href))
				if newurl in items:
					continue
				
				# Keep it for a bit
				items[newurl] = (now, newurl, description)
		
		# Otherwise, go the easy way
		else:
			# Parse it with BeautifulSoup
			soup = BeautifulSoup()
			soup.feed(resp.data)
			
			t4
			
			# Find all of the torrent URLs
			links = soup('a', {'href': '%.torrent%'})
			if not links:
				self.putlog(LOG_WARNING, "Page parsing failed: links.")
				return
			
			for link in links:
				# Build the new URL
				newurl = UnquoteHTML(UnquoteURL(urlparse.urljoin(resp.url, link['href'])))
				if newurl in items:
					continue
				
				# Get some text to describe it
				desc = str(link.contents[0])
				
				lines = StripHTML(desc)
				if len(lines) != 1:
					continue
				
				# Keep it for a bit
				items[newurl] = (now, newurl, lines[0])
		
		t5 = time.time()
		
		# If we found nothing, bug out
		if items == {}:
			tolog = "Found no torrents at %s!" % resp.url
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Switch back to a list
		items = items.values()
		items.sort()
		
		# Build our query
		trigger.items = items
		
		args = [item[1] for item in items] + [item[2] for item in items]
		querybit = ', '.join(['%s'] * len(items))
		
		query = SELECT_QUERY % (querybit, querybit)
		
		print 'Page parsed: %.3fs %.3fs %.3fs %.3fs %.3fs' % (time.time() - t4, t4 - t3, t3 - t2, t2 - t1)
		
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
		
		# We don't need to add any that are already in the database
		for row in result:
			lurl = row['url'].lower()
			ldesc = row['description'].lower()
			items = [a for a in items if a[1].lower() != lurl and a[2].lower() != ldesc]
		
		# Start adding any items to our database
		for item in items:
			self.dbQuery(trigger, None, INSERT_QUERY, *item)
	
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
<ttl>%s</ttl>""" % (builddate, int(self.Options['rss_interval']) * 60)
		
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
