# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

import os
import re
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

SCRAPE_TIMER = 'SCRAPE_TIMER'

SELECT_QUERY = "SELECT url, description FROM torrents WHERE url = %s"
RECENT_QUERY = "SELECT url, description FROM torrents ORDER BY added DESC LIMIT 20"
INSERT_QUERY = "INSERT INTO torrents (added, url, description) VALUES (%s,%s,%s)"

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
		self.setTimedEvent(SCRAPE_TIMER, 60, None)
		
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# Get some URLs that haven't been checked recently
	def _trigger_SCRAPE_TIMER(self, trigger):
		interval = int(self.Options['scrape_interval']) * 60
		now = time.time()
		
		ready = [k for k, v in self.URLs.items() if now - v > interval]
		for url in ready[:int(self.Options['urls_per_minute'])]:
			self.URLs[url] = now
			self.urlRequest(trigger, self.__Parse_Page, url)
	
	# -----------------------------------------------------------------------
	# Do some page parsing!
	def __Parse_Page(self, trigger, resp):
		# Find all of our URLs
		chunks = FindChunks(resp.data, '<a ', '</a>')
		if not chunks:
			#self.sendReply(trigger, 'Page parsing failed: links.')
			self.putlog(LOG_WARNING, "Page parsing failed: links.")
			return
		
		# See if any are talking about torrents
		items = []
		now = int(time.time())
		
		for chunk in chunks:
			# Find the URL
			href = FindChunk(chunk, 'href="', '"')
			if not href or href.find('.torrent') < 0:
				continue
			
			# Build the new URL
			newurl = urlparse.urljoin(resp.url, href)
			
			# Get some text to describe it
			bits = chunk.split('>', 1)
			if len(bits) != 2:
				continue
			
			lines = StripHTML(bits[1])
			if len(lines) != 1:
				continue
			
			# Keep it for a bit
			items.append((now, newurl, lines[0]))
		
		# If we found nothing, bug out
		if items == []:
			tolog = "Found no torrents at %s!" % resp.url
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Build our query
		trigger.items = items
		
		query = SELECT_QUERY
		args = [items[0][1]]
		
		for ctime, url, description in items[1:]:
			query = query + ' OR url = %s'
			args.append(url)
		
		# And execute it
		self.dbQuery(trigger, self.__DB_Check, query, *args)
	
	# -----------------------------------------------------------------------
	# Handle the check reply
	def __DB_Check(self, trigger, result):
		# Error!
		if result is None:
			self.putlog(LOG_WARNING, '__DB_Check: A DB error occurred!')
			return
		
		items = trigger.items
		del trigger.items
		
		# We don't need to add any that are already in the database
		for row in result:
			eatme = [a for a in items if a[1].lower() == row['url'].lower()]
			for eat in eatme:
				items.remove(eat)
		
		# If we don't have any new items, go home now
		if items == []:
			return
		
		# Start adding the items to our database
		item = items.pop(0)
		trigger.items = items
		self.dbQuery(trigger, self.__DB_Inserted, INSERT_QUERY, *item)
	
	# An item has been inserted, try the next one if we have to
	def __DB_Inserted(self, trigger, result):
		# Error, just log it, we want to keep inserting news items
		if result is None:
			self.putlog(LOG_WARNING, '__DB_Inserted: A DB error occurred!')
		
		# If we have no more articles, go home now
		if len(trigger.items) == 0:
			del trigger.items
			return
		
		# Do the next one
		item = trigger.items.pop(0)
		self.dbQuery(trigger, self.__DB_Inserted, INSERT_QUERY, *item)

# ---------------------------------------------------------------------------
