# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Gathers news from Ananova Quirkies, Google News or any RSS feeds you might
want to use.
"""

import re
import time
import types

from random import Random
#from sgmllib import SGMLParseError

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

from classes.feedparser import FeedParser

# ---------------------------------------------------------------------------

NEWS_SEARCH_MAX_RESULTS = 6

MAX_TITLE_LENGTH = 200

# ---------------------------------------------------------------------------

NEWS_QUERY = 'SELECT title, url, description FROM news WHERE title IN (%s) OR url IN (%s)'
INSERT_QUERY = 'INSERT INTO news (title, url, description, added) VALUES (%s,%s,%s,%s)'
TIME_QUERY = 'DELETE FROM news WHERE added < %s'
SEARCH_QUERY = 'SELECT title, url, description FROM news WHERE %s'

# ---------------------------------------------------------------------------

ANANOVA_QUIRKIES_URL = 'http://www.ananova.com/news/lp.html?keywords=Quirkies&menu=news.quirkies'
GOOGLE_BUSINESS_URL = 'http://news.google.com/news/en/us/business.html'
GOOGLE_HEALTH_URL = 'http://news.google.com/news/en/us/health.html'
GOOGLE_SCIENCE_URL = 'http://news.google.com/news/en/us/technology.html'
GOOGLE_SPORT_URL = 'http://news.google.com/news/en/us/sports.html'
GOOGLE_WORLD_URL = 'http://news.google.com/news/en/us/world.html'

# ---------------------------------------------------------------------------

GOOGLE_STORY_TITLE_RE = re.compile(r'<a class=y href="/url\?ntc=\S+&q=(.*?)">(.*?)</a>')
GOOGLE_STORY_TEXT_RE = re.compile(r'</b><br>(.*?)<br>')

# ---------------------------------------------------------------------------

class News(Plugin):
	"""
	A news gatherer plugin.
	
	This will search for updated news stories on Google News and Ananova
	Quirkies (!), and reply with the title of and link to any that it finds.
	"""
	
	def setup(self):
		# Load our outgoing queue
		self.__outgoing = self.loadPickle('.news.outgoing') or []
		if self.__outgoing:
			tolog = '%d news item(s) loaded into outgoing queue' % len(self.__outgoing)
			self.putlog(LOG_ALWAYS, tolog)
		
		currtime = time.time()
		self.__Last_Clearout_Time = currtime
		
		self.__rand_gen = Random(currtime)
		
		self.rehash()
	
	def rehash(self):
		# Load our options into something easier to use
		self.News_Options = self.SetupOptions('News')
		self.RSS_Options = self.SetupOptions('RSS')
		
		# Set up our error reporting thing
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
		
		# Set up our news targets
		self.__Setup_News_Targets()
		
		# Setup our RSS feeds
		self.__Setup_RSS_Feeds()
	
	# Make extra sure our news queue is saved
	def shutdown(self, message):
		self.savePickle('.news.outgoing', self.__outgoing)
	
	# -----------------------------------------------------------------------
	# Set up the target dictionaries for our Ananova/Google spam
	def __Setup_News_Targets(self):
		self.__Targets = {
			'ananova_quirkies': {},
			'google_business': {},
			'google_health': {},
			'google_science': {},
			'google_sport': {},
			'google_world': {},
			'rss_default': {},
		}
		
		# Try splitting our News options into store/network bits
		for option, value in self.News_Options.items():
			bits = option.split('.', 1)
			if len(bits) == 2 and bits[0] in self.__Targets:
				self.__Targets[bits[0]][bits[1]] = value.split()
		
		# Now see if we have some RSS defaults
		for option, value in self.RSS_Options.items():
			if option.startswith('default_targets.'):
				network = option.split('.', 1)[1]
				self.__Targets['rss_default'][network] = value.split()
	
	# -----------------------------------------------------------------------
	# Do stuff
	def __Setup_RSS_Feeds(self):
		self.RSS_Feeds = {}
		
		currtime = time.time()
		
		for section in self.Config.sections():
			if not section.startswith('RSS.'):
				continue
			
			name = section.split('.', 1)[1]
			
			feed = {}
			
			if self.Config.has_option(section, 'title'):
				feed['title'] = self.Config.get(section, 'title')
			else:
				feed['title'] = None
			
			if self.Config.has_option(section, 'maximum_new'):
				feed['maximum_new'] = self.Config.getint(section, 'maximum_new')
			else:
				feed['maximum_new'] = self.RSS_Options['maximum_new']
			
			if self.Config.has_option(section, 'interval'):
				feed['interval'] = self.Config.getint(section, 'interval')
			else:
				feed['interval'] = self.RSS_Options['default_interval']
			feed['checked'] = currtime
			
			feed['url'] = self.Config.get(section, 'url')
			
			feed['last-modified'] = None
			
			self.__Setup_RSS_Target(section, feed)
			self.RSS_Feeds[name] = feed
		
		# If we found some feeds, we'll be needing a parser
		if self.RSS_Feeds:
			self.__Parser = FeedParser()
	
	def __Setup_RSS_Target(self, section, feed):
		feed['targets'] = {}
		
		# Try to find some targets for this feed
		for option in self.Config.options(section):
			bits = option.split('.', 1)
			if len(bits) == 2 and bits[0].startswith('targets'):
				feed['targets'][bits[1]] = self.Config.get(section, option).split()
		
		# Couldn't find any, use the default
		if not feed['targets']:
			feed['targets'] = self.__Targets['rss_default']
	
	# -----------------------------------------------------------------------
	# Register all our news pages that we want to check
	def register(self):
		# Various timed news checks
		if self.News_Options['ananova_quirkies_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Ananova_Quirkies,
				interval = self.News_Options['ananova_quirkies_interval'],
				targets = self.__Targets['ananova_quirkies'],
			)
		if self.News_Options['google_business_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Business,
				interval = self.News_Options['google_business_interval'],
				targets = self.__Targets['google_business'],
			)
		if self.News_Options['google_health_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Health,
				interval = self.News_Options['google_health_interval'],
				targets = self.__Targets['google_health'],
			)
		if self.News_Options['google_science_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Science,
				interval = self.News_Options['google_science_interval'],
				targets = self.__Targets['google_science'],
			)
		if self.News_Options['google_sport_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_Sport,
				interval = self.News_Options['google_sport_interval'],
				targets = self.__Targets['google_sport'],
			)
		if self.News_Options['google_world_interval']:
			self.addTimedEvent(
				method = self.__Fetch_Google_World,
				interval = self.News_Options['google_world_interval'],
				targets = self.__Targets['google_world'],
			)
		# News search
		self.addTextEvent(
			method = self.__Query_Search,
			regexp = re.compile("^news (?P<search_text>.+)$"),
			help = ('news', 'news', "\02news\02 <partial headline> : Search through recent news headlines for any stories matching the partial headline given. If exactly one story is found, the URL for it will be given."),
		)
		# RSS feed commands
		self.addTextEvent(
			method = self.__Feed_List,
			regexp = re.compile(r'^listfeeds$'),
			help = ('news', 'listfeeds', "\02listfeeds\02 : List the RSS feeds currently configured."),
		)
		self.addTextEvent(
			method = self.__Feed_Show,
			regexp = re.compile(r'^showfeed (?P<feed>.+)$'),
			help = ('news', 'showfeed', "\02showfeed\02 <feed name> : Show some information about an RSS feed."),
		)
		# RSS feeds should be checked for readiness every 30 seconds
		if self.RSS_Feeds:
			self.addTimedEvent(
				method = self.__RSS_Check,
				interval = 10,
			)
			tolog = 'Registered %d RSS feeds' % len(self.RSS_Feeds)
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
		
		now = time.time()
		old = now - self.__old_threshold
		self.__Last_Clearout_Time = now
		
		self.dbQuery(trigger, None, TIME_QUERY, old)
	
	# Search for some news
	def __Query_Search(self, trigger):
		search_text = trigger.match.group('search_text')
		if len(search_text) < 5:
			self.sendReply(trigger, 'Search query is too short!')
		elif len(search_text) > 50:
			self.sendReply(trigger, 'Search query is too long!')
		else:
			search_text = search_text.replace("%", "\%")
			search_text = search_text.replace('"', '\\\"')
			search_text = search_text.replace("'", "\\\'")
			
			words = search_text.split()
			
			if len(words) > 8:
				self.sendReply(trigger, 'Search query contains too many words!')
			
			else:
				# We need to build a bit of a crazy query here
				crits = []
				args = []
				
				for word in words:
					crit = 'title LIKE %s'
					crits.append(crit)
					arg = '%%%s%%' % word
					args.append(arg)
				
				# Off we go
				query = SEARCH_QUERY % (' AND '.join(crits))
				self.dbQuery(trigger, self.__News_Searched, query, *args)
	
	# Spam some news
	def __Spam_News(self, trigger):
		if not self.__outgoing:
			return
		
		# We pull out a random item from our outgoing list so that we
		# don't end up posting slabs of stories from the same site.
		index = self.__rand_gen.randint(0, len(self.__outgoing) - 1)
		reply = self.__outgoing.pop(index)
		
		# Spit it out
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
		
		tolog = "%s news item(s) remaining in outgoing queue" % len(self.__outgoing)
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	# List of feeds
	def __Feed_List(self, trigger):
		names = self.RSS_Feeds.keys()
		if names:
			names.sort()
			replytext = 'I currently check \x02%d\x02 RSS feeds: %s' % (len(names), ', '.join(names))
		else:
			replytext = 'Sorry, I have no RSS feeds configured.'
		self.sendReply(trigger, replytext)
	
	# Show info about an RSS feed
	def __Feed_Show(self, trigger):
		findme = trigger.match.group('feed').lower()
		matches = [name for name in self.RSS_Feeds.keys() if name.lower() == findme]
		if matches:
			feed = self.RSS_Feeds[matches[0]]
			replytext = "'%s' is %s every %d seconds" % (matches[0], feed['url'], feed['interval'])
		else:
			replytext = 'Sorry, no feed by that name.'
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def __Fetch_Ananova_Quirkies(self, trigger):
		self.urlRequest(trigger, self.__Parse_Ananova, ANANOVA_QUIRKIES_URL)
	
	def __Fetch_Google_Business(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_BUSINESS_URL)
	
	def __Fetch_Google_Health(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_HEALTH_URL)
	
	def __Fetch_Google_Science(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_SCIENCE_URL)
	
	def __Fetch_Google_Sport(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_SPORT_URL)
	
	def __Fetch_Google_World(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_WORLD_URL)
	
	# See if any feeds should be triggering around about now
	def __RSS_Check(self, trigger):
		currtime = time.time()
		
		ready = [(feed['checked'], name, feed) for name, feed in self.RSS_Feeds.items() if currtime - feed['checked'] >= feed['interval']]
		ready.sort()
		
		for checked, name, feed in ready[:1]:
			feed['checked'] = currtime
			
			# Build a fake timed event trigger
			new_trigger = PluginTimedTrigger('__FAKE__RSS__', 1, feed['targets'], [name])
			
			# Maybe send a If-Modified-Since header
			if feed['last-modified'] is not None:
				headers = {'If-Modified-Since': feed['last-modified']}
				self.urlRequest(new_trigger, self.__Parse_RSS, feed['url'], headers=headers)
			else:
				self.urlRequest(new_trigger, self.__Parse_RSS, feed['url'])
	
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
		tables = FindChunks(resp.data, '<table', '</table>')
		if not tables:
			self.putlog(LOG_WARNING, 'Google News parsing failed')
			return
		
		# See if any of them have articles
		articles = []
		
		for table in tables:
			if table.find('<a class=y') >= 0:
				# Look for the URL and story title
				m = GOOGLE_STORY_TITLE_RE.search(table)
				if not m:
					continue
				
				url, title = m.groups()
				
				# Look for the story text
				m = GOOGLE_STORY_TEXT_RE.search(table)
				if not m:
					description = ''
				else:
					description = m.group(1).strip()
				
				data = [title, url, description]
				articles.append(data)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# Parse an RSS feed!
	def __Parse_RSS(self, trigger, resp):
		started = time.time()
		
		# If it hasn't been modified, we can continue on our merry way
		if resp.response == '304':
			return
		
		# We need to leave the ampersands in for feedparser
		resp.data = UnquoteHTML(resp.data, 'amp')
		
		# Get our feed info
		name = trigger.args[0]
		feed = self.RSS_Feeds[name]
		
		# Try to parse it
		try:
			r = self.__Parser
			r.reset()
			r.feed(resp.data)
		
		except Exception, msg:
			tolog = "Error parsing RSS feed '%s': %s" % (name, msg)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Remember the Last-Modified header if it was sent
		feed['last-modified'] = resp.headers.get('Last-Modified', None)
		
		# Work out the feed title
		if feed['title']:
			feed_title = feed['title']
		else:
			feed_title = r.channel.get('title', name)
		
		# Get any articles out of the feed
		articles = []
		
		for item in r.items[:feed['maximum_new']]:
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
				# feedparser gives us weird results sometimes
				if type(item['link']) == types.ListType:
					continue
				else:
					article_link = item['link']
			
			description = item.get('description', '')
			
			# Get rid of any annoying quoted HTML and eat any tabs
			article_title = UnquoteHTML(article_title).replace('\t', ' ')
			article_link = UnquoteHTML(article_link)
			description = UnquoteHTML(description).replace('\t', ' ')
			
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
		
		articles = trigger.articles
		del trigger.articles
		
		# This way is anywhere from 2 to 20 times faster than the old way.
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
			
			# stick it in the outgoing queue
			reply = PluginReply(trigger, replytext)
			self.__outgoing.append(reply)
			
			# Insert it into the DB
			self.dbQuery(trigger, None, INSERT_QUERY, title, url, description, ctime)
	
	# -----------------------------------------------------------------------
	# Search for a news article in our news db that matches the partial title
	# we were given by a user on irc
	def __News_Searched(self, trigger, result):
		search_text = trigger.match.group('search_text')
		
		# Error!
		if result is None:
			replytext = 'An unknown database error occurred.'
			self.putlog(LOG_WARNING, '__News_Searched: A DB error occurred!')
		
		# No matches
		elif result == ():
			replytext = "No headlines in the last %d days found matching '\02%s\02'" % (self.__old_days, search_text)
		
		# Some matches
		else:
			# Too many matches
			if len(result) > NEWS_SEARCH_MAX_RESULTS:
				replytext = "Search for '\02%s\02' yielded too many results (%d > %d). Please refine your query." % (search_text, len(result), NEWS_SEARCH_MAX_RESULTS)
			
			# We found more than one and less than the max number of items
			elif len(result) > 1:
				titles = []
				for row in result:
					title = '\02[\02%s\02]\02' % row['title']
					titles.append(title)
				
				replytext = 'Found \02%d\02 headlines: %s' % (len(result), ' '.join(titles))
			
			# We found exactly one item
			else:
				if result[0]['description']:
					replytext = '%(title)s - %(url)s : %(description)s' % result[0]
				else:
					replytext = '%(title)s - %(url)s' % result[0]
		
		# Spit out a reply
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
