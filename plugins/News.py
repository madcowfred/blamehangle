# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Gathers news from Ananova Quirkies, Google News or any RSS feeds you might
want to use.
"""

import random
import re
import time
import types
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin
from classes.SimpleRSSParser import SimpleRSSParser

# ---------------------------------------------------------------------------
# Chop titles that are longer than this
MAX_TITLE_LENGTH = 200
# Search limit
SEARCH_LIMIT = 100

# ---------------------------------------------------------------------------

NEWS_QUERY = 'SELECT title, url, description FROM news WHERE title IN (%s) OR url IN (%s)'
INSERT_QUERY = 'INSERT INTO news (title, url, description, added) VALUES (%s,%s,%s,%s)'
TIME_QUERY = 'DELETE FROM news WHERE added < %s'
SEARCH_QUERY = 'SELECT title, url, description, added FROM news WHERE %s ORDER BY added DESC LIMIT ' + str(SEARCH_LIMIT)

# ---------------------------------------------------------------------------

ANANOVA_QUIRKIES_URL = 'http://www.ananova.com/news/lp.html?keywords=Quirkies&menu=news.quirkies'
GOOGLE_BUSINESS_URL = 'http://news.google.com/?ned=%s&topic=b'
GOOGLE_HEALTH_URL = 'http://news.google.com/?ned=%s&topic=m'
GOOGLE_SCIENCE_URL = 'http://news.google.com/?ned=%s&topic=t'
GOOGLE_SPORT_URL = 'http://news.google.com/?ned=%s&topic=s'
GOOGLE_WORLD_URL = 'http://news.google.com/?ned=%s&topic=w'

# ---------------------------------------------------------------------------
# Dirty dirty regexps
GOOGLE_STORY_TITLE_RE = re.compile(r'<td valign=top><a href="(http://.*?)" id=.*?><b>(.*?)</b>')
GOOGLE_STORY_TEXT_RE = re.compile(r'<font size=-1>(?!<)(.*?)</font>')

# ---------------------------------------------------------------------------

class News(Plugin):
	"""
	A news gatherer plugin.
	
	This will search for updated news stories on Google News and Ananova
	Quirkies (!), and reply with the title of and link to any that it finds.
	"""
	
	_HelpSection = 'news'
	_UsesDatabase = 'News'
	
	def setup(self):
		# Load our outgoing queue
		self.__outgoing = self.loadPickle('.news_queue') or []
		if self.__outgoing:
			tolog = '%d news item(s) loaded into outgoing queue' % len(self.__outgoing)
			self.putlog(LOG_ALWAYS, tolog)
		
		self._RSS_Feeds = {}
		
		self.rehash()
	
	def rehash(self):
		# Load our options into something easier to use
		self.News_Options = self.OptionsDict('News', autosplit=True)
		self.RSS_Options = self.OptionsDict('RSS', autosplit=True)
		
		# Set up our error reporting mess
		if hasattr(self, '_QuietURLErrors'):
			del self._QuietURLErrors
		if hasattr(self, '_VerboseURLErrors'):
			del self._VerboseURLErrors
		
		error_type = self.News_Options.get('error_type', 'normal')
		if error_type == 'quiet':
			self._QuietURLErrors = 1
		elif error_type == 'verbose':
			self._VerboseURLErrors = 1
		
		# Some old stuff that needs to be fixed
		self.__old_days = self.Config.getint('News', 'old_threshold')
		self.__old_threshold = self.__old_days * 86400
		
		# Set up our targets dict
		self._Targets = {}
		for target in ('ananova_quirkies', 'google_business', 'google_health', 'google_science', 'google_sport', 'google_world'):
			self._Targets[target] = self.News_Options.pop(target, {})
		self._Targets['rss_default'] = self.RSS_Options.pop('default_targets', {})
		
		# Update our RSS feed list
		currtime = time.time()
		sections = [s for s in self.Config.sections() if s.startswith('RSS.')]
		for section in sections:
			feedopts = self.OptionsDict(section, autosplit=True)
			name = section.split('.', 1)[1]
			
			feed = {
				'url': feedopts['url'],
				'title': feedopts.get('title', None),
				'interval': feedopts.get('interval', self.RSS_Options['default_interval']),
				'maximum_new': feedopts.get('maximum_new', self.RSS_Options['default_maximum_new']),
				'find_real_url': feedopts.get('find_real_url', 0),
				'targets': feedopts.get('targets', self._Targets['rss_default']),
				'checked': currtime,
				'last-modified': None,
			}
			
			# If the feed is new, just add it to the list
			if name not in self._RSS_Feeds:
				self._RSS_Feeds[name] = feed
			# It's already there, just update the bits we need to update
			else:
				for k in feed.keys():
					if k not in ('checked', 'last-modified'):
						self._RSS_Feeds[name][k] = feed[k]
		
		# And remove any that are no longer around
		for name in self._RSS_Feeds.keys():
			section = 'RSS.%s' % name
			if section not in sections:
				del self._RSS_Feeds[name]
	
	# Make extra sure our news queue is saved
	def shutdown(self, message):
		self.savePickle('.news_queue', self.__outgoing)
	
	# -----------------------------------------------------------------------
	# Register all our news pages that we want to check
	def register(self):
		# Various timed news checks
		if self.News_Options['ananova_quirkies_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Ananova_Quirkies,
				interval = self.News_Options['ananova_quirkies_interval'],
				targets = self._Targets['ananova_quirkies'],
			)
		if self.News_Options['google_business_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Business,
				interval = self.News_Options['google_business_interval'],
				targets = self._Targets['google_business'],
			)
		if self.News_Options['google_health_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Health,
				interval = self.News_Options['google_health_interval'],
				targets = self._Targets['google_health'],
			)
		if self.News_Options['google_science_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Science,
				interval = self.News_Options['google_science_interval'],
				targets = self._Targets['google_science'],
			)
		if self.News_Options['google_sport_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Sport,
				interval = self.News_Options['google_sport_interval'],
				targets = self._Targets['google_sport'],
			)
		if self.News_Options['google_world_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_World,
				interval = self.News_Options['google_world_interval'],
				targets = self._Targets['google_world'],
			)
		# News search
		self.addTextEvent(
			method = self.__Query_Search,
			regexp = r'^findnews (?P<findme>.+)$',
			help = ('findnews', "\02findnews\02 <search terms> : Search through recent news headlines for any stories matching the search terms given. If exactly one story is found, the URL for it will be given."),
		)
		# RSS feed commands
		self.addTextEvent(
			method = self.__Feed_List,
			regexp = r'^listfeeds$',
			help = ('listfeeds', "\02listfeeds\02 : List the RSS feeds currently configured."),
		)
		self.addTextEvent(
			method = self.__Feed_Show,
			regexp = r'^showfeed (?P<feed>.+)$',
			help = ('showfeed', "\02showfeed\02 <feed name> : Show some information about an RSS feed."),
		)
		# RSS feeds should be checked for readiness every 10 seconds
		if self._RSS_Feeds:
			self.addTimedEvent(
				method = self.__RSS_Check,
				interval = 10,
			)
			tolog = 'Registered %d RSS feed(s)' % (len(self._RSS_Feeds))
			self.putlog(LOG_ALWAYS, tolog)
		# Timed event for cleaning up the database once an hour
		self.addTimedEvent(
			method = self.__Query_Cleanup,
			interval = 3600,
		)
		# Timed event for spitting out news
		self.addTimedEvent(
			method = self.__Spam_News,
			interval = self.News_Options['spam_delay'],
		)
	
	# -----------------------------------------------------------------------
	# Cleanup old news
	def __Query_Cleanup(self, trigger):
		self.putlog(LOG_DEBUG, 'Purging old news')
		
		old = int(time.time()) - self.__old_threshold
		self.dbQuery(trigger, None, TIME_QUERY, old)
	
	# Search for some news
	def __Query_Search(self, trigger):
		findme = trigger.match.group('findme')
		
		if len(findme) < 3:
			self.sendReply(trigger, 'Search query is too short (< 3)!')
		else:
			findme = findme.replace('%', '\\%')
			crits, args = ParseSearchString('title', findme)
			
			# Off we go
			query = SEARCH_QUERY % (' AND '.join(crits))
			self.dbQuery(trigger, self.__News_Searched, query, *args)
	
	# Spam some news
	def __Spam_News(self, trigger):
		if not self.__outgoing:
			return
		
		# We pull out a random item from our outgoing list to try and avoid
		# posting slabs of stories from the same site.
		index = random.randint(0, len(self.__outgoing) - 1)
		source, replytext = self.__outgoing.pop(index)
		
		# See if we can find some targets
		targets = {}
		if source in self._Targets:
			targets = self._Targets[source]
		elif source in self._RSS_Feeds:
			targets = self._RSS_Feeds[source]['targets']
		
		# No targets... kill everything for that feed and try again
		if not targets:
			tolog = "Found news item for '%s' but it has no targets!" % (source)
			self.putlog(LOG_DEBUG, tolog)
			
			self.__outgoing = [i for i in self.__outgoing if i[0] != source]
			if self.__outgoing:
				self.__Spam_News(trigger)
			return
		
		# Spit it out
		self.privmsg(targets, None, replytext)
		
		tolog = "%s news item(s) remaining in outgoing queue" % (len(self.__outgoing))
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	# List of feeds
	def __Feed_List(self, trigger):
		names = self._RSS_Feeds.keys()
		if names:
			names.sort()
			replytext = 'I currently check \x02%d\x02 RSS feeds: %s' % (len(names), ', '.join(names))
		else:
			replytext = 'Sorry, I have no RSS feeds configured.'
		self.sendReply(trigger, replytext)
	
	# Show info about an RSS feed
	def __Feed_Show(self, trigger):
		findme = trigger.match.group('feed').lower()
		matches = [name for name in self._RSS_Feeds.keys() if name.lower() == findme]
		if matches:
			feed = self._RSS_Feeds[matches[0]]
			replytext = "'%s' is %s every %d seconds" % (matches[0], feed['url'], feed['interval'])
		else:
			replytext = 'Sorry, no feed by that name.'
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def __Fetch_Ananova_Quirkies(self, trigger):
		trigger.source = 'ananova_quirkies'
		self.urlRequest(trigger, self.__Parse_Ananova, ANANOVA_QUIRKIES_URL)
	
	def __Fetch_Google_Business(self, trigger):
		trigger.source = 'google_business'
		url = GOOGLE_BUSINESS_URL % (self.News_Options['google_news_country'])
		self.urlRequest(trigger, self.__Parse_Google, url)
	
	def __Fetch_Google_Health(self, trigger):
		trigger.source = 'google_health'
		url = GOOGLE_HEALTH_URL % (self.News_Options['google_news_country'])
		self.urlRequest(trigger, self.__Parse_Google, url)
	
	def __Fetch_Google_Science(self, trigger):
		trigger.source = 'google_science'
		url = GOOGLE_SCIENCE_URL % (self.News_Options['google_news_country'])
		self.urlRequest(trigger, self.__Parse_Google, url)
	
	def __Fetch_Google_Sport(self, trigger):
		trigger.source = 'google_sport'
		url = GOOGLE_SPORT_URL % (self.News_Options['google_news_country'])
		self.urlRequest(trigger, self.__Parse_Google, url)
	
	def __Fetch_Google_World(self, trigger):
		trigger.source = 'google_world'
		url = GOOGLE_WORLD_URL % (self.News_Options['google_news_country'])
		self.urlRequest(trigger, self.__Parse_Google, url)
	
	# See if any feeds should be triggering around about now
	def __RSS_Check(self, trigger):
		currtime = time.time()
		
		ready = [(feed['checked'], name, feed) for name, feed in self._RSS_Feeds.items() if currtime - feed['checked'] >= feed['interval']]
		ready.sort()
		
		for checked, name, feed in ready[:1]:
			trigger.source = name
			feed['checked'] = currtime
			
			# Maybe send a If-Modified-Since header
			if feed['last-modified'] is not None:
				headers = {'If-Modified-Since': feed['last-modified']}
				self.urlRequest(trigger, self.__Parse_RSS, feed['url'], headers=headers)
			else:
				self.urlRequest(trigger, self.__Parse_RSS, feed['url'])
	
	# -----------------------------------------------------------------------
	# Parse Ananova News!
	def __Parse_Ananova(self, trigger, resp):
		resp.data = UnquoteHTML(resp.data)
		
		# Find some articles
		chunks = FindChunks(resp.data, '<a href="./', '</p>')
		if not chunks:
			self.putlog(LOG_WARNING, 'Ananova Quirkies parsing failed')
			return
		
		# See if any of them will match
		articles = []
		
		for chunk in chunks:
			# Look for the story URL
			n = chunk.find('?menu=')
			if n < 0:
				continue
			url = '%s/%s' % ('http://www.ananova.com/news', chunk[:n])
			
			# Look for the story title
			title = FindChunk(chunk, 'title="', '">')
			if not title:
				continue
			
			# Look for the story description
			description = FindChunk(chunk, '<small>', '</small>') or ''
			
			# And keep it for later
			data = [title, url, description]
			articles.append(data)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# Parse Google News!
	def __Parse_Google(self, trigger, resp):
		resp.data = UnquoteHTML(resp.data)
		
		# Find some tables
		tables = FindChunks(resp.data, '<table border=0 width=75% valign=top', '</table>')
		if not tables:
			self.putlog(LOG_WARNING, 'Google News parsing failed: no artice tables.')
			return
		
		# See if any of them have articles
		articles = []
		
		for table in tables:
			# Look for the URL and story title
			m = GOOGLE_STORY_TITLE_RE.search(table)
			if not m:
				continue
			
			url, title = m.groups()
			
			# Remove any annoying bold tags
			title = title.replace(' <b>...', '...')
			
			# Look for the story text
			m = GOOGLE_STORY_TEXT_RE.search(table)
			if m:
				description = m.group(1).strip()
			else:
				description = ''
			
			data = [title, url, description]
			articles.append(data)
		
		# If we got no articles, cry here
		if not articles:
			self.putlog(LOG_WARNING, "Google News parsing failed: no articles.")
		# Go for it!
		else:
			self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# Parse an RSS feed!
	def __Parse_RSS(self, trigger, resp):
		# If it hasn't been modified, we can continue on our merry way
		if resp.response == '304':
			return

		started = time.time()
		
		# Unquote our data, HTML entities suck
		resp.data = UnquoteHTML(resp.data)
		
		# Get our feed info
		name = trigger.source
		feed = self._RSS_Feeds[name]
		
		# Try to parse it
		try:
			rss = SimpleRSSParser(resp.data)
		
		except Exception, msg:
			tolog = "Error parsing RSS feed '%s': %s" % (name, msg)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Remember the Last-Modified header if it was sent
		feed['last-modified'] = resp.headers.get('last-modified', None)
		
		# Work out the feed title
		feed_title = feed['title'] or rss['feed']['title']
		
		# Get any articles out of the feed
		articles = []
		
		for item in rss['items'][:feed['maximum_new']]:
			item_title = item.get('title', '<No Title>').strip() or '<No Title>'
			article_title = '%s: %s' % (feed_title, item_title)
			
			# If we're ignoring items with no links, log and move on
			if not item.has_key('link'):
				if self.RSS_Options['ignore_no_link']:
					tolog = "RSS item '%s' has no link!" % item_title
					self.putlog(LOG_DEBUG, tolog)
					continue
				article_link = '<No Link>'
			else:
				article_link = item['link'] or ''
			
			# If we have to, see if we can find a real URL
			if feed['find_real_url']:
				parsed = urlparse.urlparse(article_link)
				if parsed[4]:
					for key, val in [s.split('=', 1) for s in parsed[4].split('&')]:
						uval = UnquoteURL(val)
						if uval.startswith('http://'):
							article_link = uval
							break
			
			# Get rid of any annoying quoted HTML and eat any tabs
			article_title = article_title.replace('\t', ' ')
			article_link = article_link.replace('\t', ' ')
			description = item.get('description', '').replace('\t', ' ')
			
			# Keep the article for later
			data = [article_title, article_link, description]
			articles.append(data)
		
		# If we found no real articles, cry a bit
		if len(articles) == 0:
			tolog = "Failed to find any items for feed '%s'!" % (name)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Log some timing info
		tolog = "Feed '%s' parsed in %.03fs" % (name, time.time() - started)
		self.putlog(LOG_DEBUG, tolog)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# We have some new stories, see if they're in the DB
	def __News_New(self, trigger, articles):
		# If we have no articles, we can go home now
		if len(articles) == 0:
			return
		
		for article in articles:
			# Chop off any ridiculously long titles
			if len(article[0]) > MAX_TITLE_LENGTH:
				article[0] = '%s...' % article[0][:MAX_TITLE_LENGTH]
			# Unquote HTTP urls
			if article[1].startswith('http://'):
				article[1] = UnquoteURL(article[1]).replace('&amp;', '&')
		
		# Build our query
		args = [article[0] for article in articles] + [article[1] for article in articles]
		querybit = ', '.join(['%s'] * len(articles))
		query = NEWS_QUERY % (querybit, querybit)
		
		# And execute
		trigger.articles = articles
		self.dbQuery(trigger, self.__News_Reply, query, *args)
	
	# -----------------------------------------------------------------------
	# We have a reply from the database, maybe insert some stuff now
	def __News_Reply(self, trigger, result):
		# Error!
		if result is None:
			self.putlog(LOG_WARNING, '__News_Reply: A DB error occurred!')
			return
		
		source = trigger.source
		articles = trigger.articles
		del trigger.source, trigger.articles
		
		# Work out which articles are actually new ones
		newarticles = []
		
		ltitles = dict([(row['title'].lower(), None) for row in result])
		lurls = dict([(row['url'].lower(), None) for row in result])
		
		now = int(time.time())
		for article in articles:
			# If we haven't seen this before, keep it for a bit
			if (article[0].lower() not in ltitles) and (article[1].lower() not in lurls):
				newarticles.append(article)
		
		# If we don't have any new articles, go home now
		if len(newarticles) == 0:
			return
		
		# Add the new articles to our outgoing queue, then start adding them
		# to the database.
		ctime = time.time()
		
		for title, url, description in newarticles:
			replytext = '%s - %s' % (title, url)
			
			# Attach the spam prefix if we have to
			if self.News_Options['spam_prefix']:
				replytext = '%s %s' % (self.News_Options['spam_prefix'], replytext)
			
			# Attach the description if we're in verbose mode
			if self.News_Options['verbose'] and description:
				replytext = '%s : %s' % (replytext, description)
			
			# Stick it in the outgoing queue
			item = (source, replytext)
			self.__outgoing.append(item)
			
			# And insert it into the DB
			self.dbQuery(trigger, None, INSERT_QUERY, title, url, description, ctime)
		
		tolog = "Added %d news item(s) to the outgoing queue" % (len(newarticles))
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	# Search for a news article in our news db that matches the partial title
	# we were given by a user on irc
	def __News_Searched(self, trigger, result):
		findme = trigger.match.group('findme')
		
		# Error!
		if result is None:
			replytext = 'An unknown database error occurred.'
			self.putlog(LOG_WARNING, '__News_Searched: A DB error occurred!')
		
		# No matches
		elif result == ():
			replytext = "No headlines in the last %d days found matching '\02%s\02'" % (self.__old_days, findme)
		
		else:
			# Some matches
			if len(result) > 1:
				search_results = self.News_Options.get('search_results', 25)
				
				if len(result) == SEARCH_LIMIT:
					results = '\02%d\02 (or more)' % (len(result))
				else:
					results = '\02%d\02' % (len(result))
				
				if len(result) > search_results:
					replytext = 'Found %s headlines, first \02%d\02' % (results, search_results)
				else:
					replytext = 'Found %s headlines' % (results)
				
				titles = []
				for row in result[:search_results]:
					title = '\02[\02%s\02]\02' % row['title']
					titles.append(title)
				
				replytext = '%s :: %s' % (replytext, ' '.join(titles))
			
			# We found exactly one item
			else:
				row = result[0]
				
				replytext = '\x02[\x02%s ago\x02]\x02 %s - %s' % (
					NiceTime(int(time.time()) - row['added']), row['title'],
					row['url'],
				)
				
				if row['description']:
					replytext = '%s : %s' % (replytext, row['description'])
		
		# Spit out a reply
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
