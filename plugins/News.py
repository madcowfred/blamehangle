# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it. Exciting stuff.

import re
import time

from random import Random
from sgmllib import SGMLParseError

# ---------------------------------------------------------------------------

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

from classes.feedparser import FeedParser

# ---------------------------------------------------------------------------

NEWS_ANANOVA_QUIRKIES = 'NEWS_ANANOVA_QUIRKIES'
NEWS_GOOGLE_BIZ = 'NEWS_GOOGLE_BIZ'
NEWS_GOOGLE_HEALTH = 'NEWS_GOOGLE_HEALTH'
NEWS_GOOGLE_SCI = 'NEWS_GOOGLE_SCI'
NEWS_GOOGLE_WORLD = 'NEWS_GOOGLE_WORLD'
NEWS_RSS = 'NEWS_RSS'

NEWS_CLEANUP = 'NEWS_CLEANUP'
NEWS_SPAM = 'NEWS_SPAM'

# ---------------------------------------------------------------------------

NEWS_SEARCH = "NEWS_SEARCH"
NEWS_SEARCH_HELP = "'\02news\02 <partial headline>' : Search through recent news headlines for any stories matching the partial headline given. If exactly one story is found, the URL for it will be given"
NEWS_SEARCH_RE = re.compile("^news (?P<search_text>.+)$")

NEWS_SEARCH_MAX_RESULTS = 6

RSS_LIST = 'RSS_LIST'
RSS_LIST_HELP = "'\x02listfeeds\x02' : List the RSS feeds currently configured"
RSS_LIST_RE = re.compile(r'^listfeeds$')

RSS_SHOW = 'RSS_SHOW'
RSS_SHOW_HELP = "'\x02showfeed\x02 <feed name>' : Show some information about an RSS feed"
RSS_SHOW_RE = re.compile(r'^showfeed (?P<feed>.+)$')

# ---------------------------------------------------------------------------

NEWS_QUERY = "SELECT title, url, description FROM news WHERE title = %s"
INSERT_QUERY = "INSERT INTO news (title, url, description, added) VALUES (%s,%s,%s,%s)"
TIME_QUERY = "DELETE FROM news WHERE added < %s"
SEARCH_QUERY = 'SELECT title, url, description FROM news WHERE %s'

# ---------------------------------------------------------------------------

ANANOVA_QUIRKIES_URL = 'http://www.ananova.com/news/index.html?keywords=Quirkies'
GOOGLE_BIZ_URL = 'http://news.google.com/news/en/us/business.html'
GOOGLE_HEALTH_URL = 'http://news.google.com/news/en/us/health.html'
GOOGLE_SCI_URL = 'http://news.google.com/news/en/us/technology.html'
GOOGLE_WORLD_URL = 'http://news.google.com/news/en/us/world.html'

# ---------------------------------------------------------------------------

ANANOVA_STORY_TITLE_RE = re.compile(r'^(story.*?)\?menu=" title="(.*?)">')
ANANOVA_STORY_TEXT_RE = re.compile(r'<small>(.*?)</small>')

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
		self.__outgoing = self.loadPickle('.news.outgoing') or []
		if self.__outgoing:
			tolog = '%d news item(s) loaded into outgoing queue' % len(self.__outgoing)
			self.putlog(LOG_ALWAYS, tolog)
		
		currtime = time.time()
		self.__Last_Clearout_Time = currtime
		
		self.__rand_gen = Random(currtime)
		
		self.__Setup_Config()
	
	def rehash(self):
		self.__Setup_Config()
	
	# Make extra sure our news queue is saved
	def shutdown(self, message):
		self.savePickle('.news.outgoing', self.__outgoing)
	
	def __Setup_Config(self):
		self.__spam_delay = self.Config.getint('News', 'spam_delay')
		self.__spam_prefix = self.Config.get('News', 'spam_prefix')
		
		self.__old_days = self.Config.getint('News', 'old_threshold')
		self.__old_threshold = self.__old_days * 86400
		
		self.__anaq_targets = {}
		self.__gbiz_targets = {}
		self.__gh_targets = {}
		self.__gsci_targets = {}
		self.__gwn_targets = {}
		self.__setup_news_targets()
		
		if self.Config.getboolean('News', 'verbose'):
			tolog = 'Using verbose mode for news'
			self.__verbose = 1
		else:
			tolog = 'Using brief mode for news'
			self.__verbose = 0
		self.putlog(LOG_DEBUG, tolog)
		
		self.__gwn_interval = self.Config.getint('News', 'google_world_interval') * 60
		self.__gsci_interval = self.Config.getint('News', 'google_sci_interval') * 60
		self.__gh_interval = self.Config.getint('News', 'google_health_interval') * 60
		self.__gbiz_interval = self.Config.getint('News', 'google_business_interval') * 60
		self.__anaq_interval = self.Config.getint('News', 'ananovaq_interval') * 60
		
		# Do RSS feed setup
		self.__rss_default_interval = self.Config.getint('RSS', 'default_interval') * 60
		self.__rss_ignore_no_link = self.Config.getboolean('RSS', 'ignore_no_link')
		self.__rss_maximum_new = max(1, self.Config.getint('RSS', 'maximum_new'))
		
		self.__Setup_RSS_Feeds()
	
	# -----------------------------------------------------------------------
	
	def __setup_news_targets(self):
		for option in self.Config.options('News'):
			if option.startswith('google_world.'):
				self.__setup_target(self.__gwn_targets, 'News', option)
			elif option.startswith('google_sci.'):
				self.__setup_target(self.__gsci_targets, 'News', option)
			elif option.startswith('google_health.'):
				self.__setup_target(self.__gh_targets, 'News', option)
			elif option.startswith('google_business.'):
				self.__setup_target(self.__gbiz_targets, 'News', option)
			elif option.startswith('ananova.'):
				self.__setup_target(self.__anaq_targets, 'News', option)
	
	# -----------------------------------------------------------------------
	
	def __setup_target(self, target_store, section, option):
		network = option.split('.')[1]
		targets = self.Config.get(section, option).split()
		target_store[network] = targets
	
	# -----------------------------------------------------------------------
	# Do stuff
	def __Setup_RSS_Feeds(self):
		self.RSS_Feeds = {}
		
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
				feed['maximum_new'] = self.__rss_maximum_new
			
			if self.Config.has_option(section, 'interval'):
				feed['interval'] = self.Config.getint(section, 'interval') * 60
			else:
				feed['interval'] = self.__rss_default_interval
			
			self.__Setup_RSS_Target(section, feed)
			
			feed['url'] = self.Config.get(section, 'url')
			
			self.RSS_Feeds[name] = feed
	
	def __Setup_RSS_Target(self, section, feed):
		feed['targets'] = {}
		for option in self.Config.options(section):
			if option.startswith('targets.'):
				self.__setup_target(feed['targets'], section, option)
		
		if not feed['targets']:
			for option in self.Config.options('RSS'):
				if option.startswith('default_targets.'):
					self.__setup_target(feed['targets'], 'RSS', option)
	
	# -----------------------------------------------------------------------
	# Register all our news pages that we want to check
	def _message_PLUGIN_REGISTER(self, message):
		# Various timed news checks
		if self.__anaq_interval:
			self.setTimedEvent(NEWS_ANANOVA_QUIRKIES, self.__anaq_interval, self.__anaq_targets)
		if self.__gbiz_interval:
			self.setTimedEvent(NEWS_GOOGLE_BIZ, self.__gbiz_interval, self.__gbiz_targets)
		if self.__gh_interval:
			self.setTimedEvent(NEWS_GOOGLE_HEALTH, self.__gh_interval, self.__gh_targets)
		if self.__gsci_interval:
			self.setTimedEvent(NEWS_GOOGLE_SCI, self.__gsci_interval, self.__gsci_targets)
		if self.__gwn_interval:
			self.setTimedEvent(NEWS_GOOGLE_WORLD, self.__gwn_interval, self.__gwn_targets)
		# News search
		self.setTextEvent(NEWS_SEARCH, NEWS_SEARCH_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# RSS feed commands
		self.setTextEvent(RSS_LIST, RSS_LIST_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(RSS_SHOW, RSS_SHOW_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# RSS feeds
		feednames = self.RSS_Feeds.keys()
		if feednames:
			feednames.sort()
			# Add a timed event for each feed
			for name in feednames:
				feed = self.RSS_Feeds[name]
				self.setTimedEvent(NEWS_RSS, feed['interval'], feed['targets'], name)
				
				tolog = 'Registering RSS feed %s: %s' % (name, feed['url'])
				self.putlog(LOG_DEBUG, tolog)
			
			tolog = "Registered %d RSS feeds" % len(feednames)
			self.putlog(LOG_ALWAYS, tolog)
		
		# Timed event for cleaning up the database once an hour
		self.setTimedEvent(NEWS_CLEANUP, 3600, {})
		# Timed event for spitting out news
		self.setTimedEvent(NEWS_SPAM, self.__spam_delay, {})
		
		# Register all these events
		self.registerEvents()
		
		# Help meeee
		self.setHelp('news', 'news', NEWS_SEARCH_HELP)
		self.setHelp('news', 'listfeeds', RSS_LIST_HELP)
		self.setHelp('news', 'showfeed', RSS_SHOW_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Cleanup old news
	def _trigger_NEWS_CLEANUP(self, trigger):
		self.putlog(LOG_DEBUG, 'Purging old news')
		
		now = time.time()
		old = now - self.__old_threshold
		self.__Last_Clearout_Time = now
		
		self.dbQuery(trigger, None, TIME_QUERY, old)
	
	# Search for some news
	def _trigger_NEWS_SEARCH(self, trigger):
		search_text = trigger.match.group('search_text')
		if len(search_text) < 5:
			self.sendReply(event, 'Search query is too short!')
		elif len(search_text) > 50:
			self.sendReply(event, 'Search query is too long!')
		else:
			search_text = search_text.replace("%", "\%")
			search_text = search_text.replace('"', '\\\"')
			search_text = search_text.replace("'", "\\\'")
			
			words = search_text.split()
			
			if len(words) > 8:
				self.sendReply(event, 'Search query contains too many words!')
			else:
				crits = []
				for word in words:
					crit = 'title like "%%%s%%"' % word
					crits.append(crit)
				critstr = ' and '.join(crits)
				
				query = SEARCH_QUERY % critstr
				self.dbQuery(trigger, self.__News_Searched, query)
	
	# Spam some news
	def _trigger_NEWS_SPAM(self, trigger):
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
	def _trigger_RSS_LIST(self, trigger):
		names = self.RSS_Feeds.keys()
		if names:
			names.sort()
			replytext = 'I currently check \x02%d\x02 RSS feeds: %s' % (len(names), ', '.join(names))
		else:
			replytext = 'Sorry, I have no RSS feeds configured.'
		self.sendReply(trigger, replytext)
	
	# Show info about an RSS feed
	def _trigger_RSS_SHOW(self, trigger):
		findme = trigger.match.group('feed').lower()
		matches = [name for name in self.RSS_Feeds.keys() if name.lower() == findme]
		if matches:
			feed = self.RSS_Feeds[matches[0]]
			replytext = "'%s' is %s every %d minutes" % (matches[0], feed['url'], feed['interval'] / 60)
		else:
			replytext = 'Sorry, no feed by that name.'
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def _trigger_NEWS_ANANOVA_QUIRKIES(self, trigger):
		self.urlRequest(trigger, self.__Parse_Ananova, ANANOVA_QUIRKIES_URL)
	
	def _trigger_NEWS_GOOGLE_BIZ(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_BIZ_URL)
	
	def _trigger_NEWS_GOOGLE_HEALTH(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_HEALTH_URL)
	
	def _trigger_NEWS_GOOGLE_SCI(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_SCI_URL)
	
	def _trigger_NEWS_GOOGLE_WORLD(self, trigger):
		self.urlRequest(trigger, self.__Parse_Google, GOOGLE_WORLD_URL)
	
	def _trigger_NEWS_RSS(self, trigger):
		name = trigger.args[0]
		if name in self.RSS_Feeds:
			feed = self.RSS_Feeds[name]
			self.urlRequest(trigger, self.__Parse_RSS, feed['url'])
	
	# -----------------------------------------------------------------------
	# Parse Ananova News!
	def __Parse_Ananova(self, trigger, page_text):
		page_text = UnquoteHTML(page_text)
		
		# Find some articles
		chunks = FindChunks(page_text, '<a href="./', '</p>')
		if not chunks:
			self.putlog(LOG_WARNING, 'Ananova Quirkies parsing failed')
			return
		
		# See if any of them will match
		articles = []
		
		for chunk in chunks:
			# Look for the URL and story title
			m = ANANOVA_STORY_TITLE_RE.search(chunk)
			if not m:
				print chunk
				print '^^STORY_TITLE^^'
				continue
			
			url = '%s/%s' % ('http://www.ananova.com/news', m.group(1))
			title = m.group(2)
			
			# Look for the description
			m = ANANOVA_STORY_TEXT_RE.search(chunk)
			if not m:
				print chunk
				print '^^STORY_TEXT^^'
				description = ''
			else:
				description = m.group(1).strip()
			
			data = [title, url, description, time.time()]
			articles.append(data)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# Parse Google News!
	def __Parse_Google(self, trigger, page_text):
		page_text = UnquoteHTML(page_text)
		
		# Find some tables
		tables = FindChunks(page_text, '<table', '</table>')
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
					print table
					print '^^STORY_TITLE^^'
					continue
				
				url, title = m.groups()
				
				# Look for the story text
				m = GOOGLE_STORY_TEXT_RE.search(table)
				if not m:
					print table
					print '^^STORY_TEXT^^'
					description = ''
				else:
					description = m.group(1).strip()
				
				data = [title, url, description, time.time()]
				articles.append(data)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# Parse an RSS feed!
	def __Parse_RSS(self, trigger, page_text):
		page_text = UnquoteHTML(page_text)
		
		name = trigger.args[0]
		feed = self.RSS_Feeds[name]
		
		r = FeedParser()
		# Catch any weird errors when feeding the text in
		try:
			r.feed(page_text)
		
		except SGMLParseError, msg:
			tolog = "Error parsing feed '%s': %s" % (feed, msg)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Work out the feed title
		if feed['title']:
			feed_title = feed['title']
		else:
			feed_title = r.channel.get('title', name)
		
		# Get any articles out of the feed
		articles = []
		
		for item in r.items[:feed['maximum_new']]:
			item_title = item.get('title', '<No Title>').strip()
			
			if self.__rss_ignore_no_link:
				if not item.has_key('link'):
					tolog = "RSS item '%s' has no link!" % item_title
					self.putlog(LOG_DEBUG, tolog)
					continue
				link = item['link']
			else:
				link = item.get('link', '<no link>')
			
			description = item.get('description', '')
			
			article_title = '%s: %s' % (feed_title, item_title)
			data = [article_title, link, description, time.time()]
			articles.append(data)
		
		# Go for it!
		self.__News_New(trigger, articles)
	
	# -----------------------------------------------------------------------
	# We have some new stories, see if they're in the DB
	def __News_New(self, trigger, articles):
		# If we have no articles, we can go home now
		if len(articles) == 0:
			return
		
		trigger.articles = articles
		
		# If we just have one article, we can go the easy way
		#
		if len(trigger.articles) == 1:
			self.dbQuery(trigger, self.__News_New, NEWS_QUERY, trigger.articles[0][0])
		
		# If we have more, construct a monster query
		else:
			query = NEWS_QUERY
			args = [trigger.articles[0][0]]
			
			for article in trigger.articles[1:]:
				query = query + ' OR title = %s'
				args.append(article[0])
			
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
		
		#tolog = '>>articles: %s' % repr(articles)
		#self.putlog(LOG_DEBUG, tolog)
		#tolog = '>>result: %s' % repr(result)
		#self.putlog(LOG_DEBUG, tolog)
		
		# We don't need to add any that are already in the database
		for row in result:
			eatme = [a for a in articles if a[0] == row['title']]
			if eatme:
				articles.remove(eatme[0])
		
		#tolog = '>>articles: %s' % repr(articles)
		#self.putlog(LOG_DEBUG, tolog)
		
		# If we don't have any new articles, go home now
		if len(articles) == 0:
			return
		
		# Add the new articles to our outgoing queue, then start adding them
		# to the database.
		for title, url, description, ctime in articles:
			if self.__verbose and description:
				replytext = '%s - %s : %s' % (title, url, description)
			else:
				replytext = '%s - %s' % (title, url)
			
			# Attach the spam prefix if we have ot
			if self.__spam_prefix:
				replytext = '%s %s' % (self.__spam_prefix, replytext)
			
			# stick it in the outgoing queue
			reply = PluginReply(trigger, replytext)
			self.__outgoing.append(reply)
		
		# Start the DB fun
		article = articles.pop(0)
		trigger.insertme = articles
		self.dbQuery(trigger, self.__News_Inserted, INSERT_QUERY, *article)
	
	# A news item has been inserted, try the next one if we have to
	def __News_Inserted(self, trigger, result):
		# Error, just log it, we want to keep inserting news items
		if result is None:
			self.putlog(LOG_WARNING, '__News_Inserted: A DB error occurred!')
		
		# If we have no more articles, go home now
		if len(trigger.insertme) == 0:
			return
		
		# Do the next one
		article = trigger.insertme.pop(0)
		self.dbQuery(trigger, self.__News_Inserted, INSERT_QUERY, *article)
	
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
			self.sendReply(trigger, replytext)
		
		# Some matches
		else:
			# Too many matches
			if len(result) > NEWS_SEARCH_MAX_RESULTS:
				replytext = "Search for '\02%s\02' yielded too many results. Please refine your query." % search_text
			
			# We found more than one and less than the max number of items
			elif len(result) > 1:
				replytext = "\02%d\02 Headlines found: " % len(results)
				while results:
					# can't use string.join() here :(
					replytext += "%s" % results[0]['title']
					results = results[1:]
					if results:
						replytext += " \02;;\02 "
			
			# We found exactly one item
			else:
				replytext = '%(title)s - %(url)s : %(description)s' % result[0]
		
		# Spit out a reply
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
