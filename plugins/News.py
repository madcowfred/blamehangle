# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it.
# exciting stuff.

#CREATE TABLE news (
#	title varchar(255) NOT NULL default '',
#	url varchar(255) default NULL,
#	description text default NULL,
#	time bigint UNSIGNED default NULL,
#	PRIMARY KEY (title)
#	) TYPE=MyISAM;

from random import Random
import cPickle
import re
import time
import types

from classes.Constants import *
from classes.Plugin import *
from classes.feedparser import FeedParser

from classes.HTMLParser import HTMLParser, HTMLParseError

# ---------------------------------------------------------------------------

NEWS_GOOGLE_WORLD = "NEWS_GOOGLE_WORLD"
NEWS_GOOGLE_SCI = "NEWS_GOOGLE_SCI"
NEWS_GOOGLE_HEALTH = "NEWS_GOOGLE_HEALTH"
NEWS_GOOGLE_BIZ = "NEWS_GOOGLE_BIZ"
NEWS_ANANOVA = "NEWS_CHECK_ANANOVA"

NEWS_RSS = "NEWS_RSS"
RSS_LIST = 'RSS_LIST'
RSS_SHOW = 'RSS_SHOW'

NEWS_INSERT = "NEWS_INSERT"
TIME_CHECK = "TIME_CHECK"

NEWS_SEARCH = "NEWS_SEARCH"
MAX_NEWS_SEARCH_RESULTS = 6

NEWS_QUERY = "SELECT title, url, description FROM news WHERE title = %s"
INSERT_QUERY = "INSERT INTO news (title, url, description, time) VALUES (%s,%s,%s,%s)"
TIME_QUERY = "DELETE FROM news WHERE time < %s"
SEARCH_QUERY = 'SELECT title, url, description FROM news WHERE %s'

NEWS_SEARCH_RE = re.compile("^news (?P<search_text>.+)$")
RSS_LIST_RE = re.compile(r'^listfeeds$')
RSS_SHOW_RE = re.compile(r'^showfeed (?P<feed>.+)$')

GOOGLE_WORLD = 'http://news.google.com/news/gnworldleftnav.html'
GOOGLE_SCI = 'http://news.google.com/news/gntechnologyleftnav.html'
GOOGLE_HEALTH = 'http://news.google.com/news/gnhealthleftnav.html'
GOOGLE_BIZ = 'http://news.google.com/news/gnbusinessleftnav.html'
ANANOVA_QUIRK = 'http://www.ananova.com/news/index.html?keywords=Quirkies'

# ---------------------------------------------------------------------------

class News(Plugin):
	"""
	A news gatherer plugin.
	
	This will search for updated news stories on Google News and Ananova
	Quirkies (!), and reply with the title of and link to any that it finds.
	"""
	
	def setup(self):
		self.__outgoing = self.__unpickle('.news.out_pickle') or []
		if self.__outgoing:
			tolog = '%d news item(s) loaded into outgoing queue' % len(self.__outgoing)
			self.putlog(LOG_DEBUG, tolog)
		
		currtime = time.time()
		
		self.__Last_Spam_Time = currtime
		self.__Last_Clearout_Time = currtime
		
		self.__rand_gen = Random(currtime)
		
		self.__setup_config()
	
	# Make extra sure our news queue is saved
	def shutdown(self, message):
		self.__pickle(self.__outgoing, '.news.out_pickle')
	
	def __setup_config(self):
		self.__spam_delay = self.Config.getint('News', 'spam_delay')
		self.__spam_prefix = self.Config.get('News', 'spam_prefix')
		
		self.__old_days = self.Config.getint('News', 'old_threshold')
		self.__old_threshold = self.__old_days * 86400
		
		self.__gwn_targets = {}
		self.__gsci_targets = {}
		self.__gh_targets = {}
		self.__gbiz_targets = {}
		self.__anaq_targets = {}
		self.__setup_news_targets()
		
		if self.Config.getboolean('News', 'verbose'):
			tolog = "Using verbose mode for news"
			self.__verbose = 1
		else:
			tolog = "Using brief mode for news"
			self.__verbose = 0
		self.putlog(LOG_DEBUG, tolog)
		
		self.__google = Google()
		self.__ananova = Ananova()
		
		
		self.__gwn_interval = self.Config.getint('News', 'google_world_interval') * 60
		self.__gsci_interval = self.Config.getint('News', 'google_sci_interval') * 60
		self.__gh_interval = self.Config.getint('News', 'google_health_interval') * 60
		self.__gbiz_interval = self.Config.getint('News', 'google_business_interval') * 60
		self.__anaq_interval = self.Config.getint('News', 'ananovaq_interval') * 60
		
		# Do RSS feed setup
		self.__rss_default_interval = self.Config.getint('RSS', 'default_interval') * 60
		self.__rss_ignore_no_link = self.Config.getboolean('RSS', 'ignore_no_link')
		self.__rss_maximum_new = min(1, self.Config.getint('RSS', 'maximum_new'))
		
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
	
	def rehash(self):
		self.__setup_config()
	
	# Register all our news pages that we want to check
	def _message_PLUGIN_REGISTER(self, message):
		gwn = PluginTimedEvent(NEWS_GOOGLE_WORLD, self.__gwn_interval, self.__gwn_targets)
		gsci = PluginTimedEvent(NEWS_GOOGLE_SCI, self.__gsci_interval, self.__gsci_targets)
		gh = PluginTimedEvent(NEWS_GOOGLE_HEALTH, self.__gh_interval, self.__gh_targets)
		gbiz = PluginTimedEvent(NEWS_GOOGLE_BIZ, self.__gbiz_interval, self.__gbiz_targets)
		anaq = PluginTimedEvent(NEWS_ANANOVA, self.__anaq_interval, self.__anaq_targets)
		
		if self.__gwn_interval:
			self.register(gwn)
		if self.__gsci_interval:
			self.register(gsci)
		if self.__gh_interval:
			self.register(gh)
		if self.__gbiz_interval:
			self.register(gbiz)
		if self.__anaq_interval:
			self.register(anaq)
		
		ns_dir = PluginTextEvent(NEWS_SEARCH, IRCT_PUBLIC_D, NEWS_SEARCH_RE)
		ns_msg = PluginTextEvent(NEWS_SEARCH, IRCT_MSG, NEWS_SEARCH_RE)
		
		self.register(ns_dir, ns_msg)
		
		# RSS feeds
		list_pub = PluginTextEvent(RSS_LIST, IRCT_PUBLIC_D, RSS_LIST_RE)
		list_msg = PluginTextEvent(RSS_LIST, IRCT_MSG, RSS_LIST_RE)
		show_pub = PluginTextEvent(RSS_SHOW, IRCT_PUBLIC_D, RSS_SHOW_RE)
		show_msg = PluginTextEvent(RSS_SHOW, IRCT_MSG, RSS_SHOW_RE)
		self.register(list_pub, list_msg, show_pub, show_msg)
		
		for name in self.RSS_Feeds:
			feed = self.RSS_Feeds[name]
			
			tolog = 'Registering RSS feed %s: %s' % (name, feed['url'])
			self.putlog(LOG_DEBUG, tolog)
			
			event = PluginTimedEvent(NEWS_RSS, feed['interval'], feed['targets'], name)
			self.register(event)
		
		
		self.__setup_help_msgs()
	
	def __setup_help_msgs(self):
		NEWS_HELP = "'\02news\02 <partial headline>' : Search through recent news headlines for any stories matching the partial headline given. If exactly one story is found, the URL for it will be given"
		
		RSS_LIST_HELP = "'\x02listfeeds\x02' : List the RSS feeds currently configured"
		RSS_SHOW_HELP = "'\x02showfeed\x02 <feed name>' : Show some information about an RSS feed"
		
		self.setHelp('news', 'news', NEWS_HELP)
		self.setHelp('news', 'listfeeds', RSS_LIST_HELP)
		self.setHelp('news', 'showfeed', RSS_SHOW_HELP)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		event = message.data
		
		if event.name == NEWS_GOOGLE_WORLD:
			self.urlRequest(event, GOOGLE_WORLD)
		elif event.name == NEWS_GOOGLE_SCI:
			self.urlRequest(event, GOOGLE_SCI)
		elif event.name == NEWS_GOOGLE_HEALTH:
			self.urlRequest(event, GOOGLE_HEALTH)
		elif event.name == NEWS_GOOGLE_BIZ:
			self.urlRequest(event, GOOGLE_BIZ)
		elif event.name == NEWS_ANANOVA:
			self.urlRequest(event, ANANOVA_QUIRK)
		
		elif event.name == NEWS_SEARCH:
			search_text = event.match.group('search_text')
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
					
					query = (SEARCH_QUERY % critstr, )
					self.dbQuery(event, query)
		
		elif event.name == NEWS_RSS:
			name = event.args[0]
			feed = self.RSS_Feeds[name]
			returnme = (event, name)
			self.urlRequest(returnme, feed['url'])
		
		elif event.name == RSS_LIST:
			names = self.RSS_Feeds.keys()
			if names:
				names.sort()
				replytext = 'I currently check \x02%d\x02 RSS feeds: %s' % (len(names), ', '.join(names))
			else:
				replytext = 'Sorry, I have no RSS feeds configured.'
			self.sendReply(event, replytext)
		
		elif event.name == RSS_SHOW:
			findme = event.match.group('feed').lower()
			matches = [name for name in self.RSS_Feeds.keys() if name.lower() == findme]
			if matches:
				feed = self.RSS_Feeds[matches[0]]
				replytext = "'%s' is %s every %d minutes" % (matches[0], feed['url'], feed['interval'] / 60)
			else:
				replytext = 'Sorry, no feed by that name.'
			self.sendReply(event, replytext)
		
		else:
			errstring = "News has no event: %s" % event.name
			raise ValueError, errstring
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		# Periodically check if we need to send some text out to IRC
		if self.__outgoing:
			if currtime - self.__Last_Spam_Time >= self.__spam_delay:
				self.__Last_Spam_Time = currtime
				
				# We pull out a random item from our outgoing list so that
				# we don't end up posting slabs of stories from the same
				# site in a row
				index = self.__rand_gen.randint(0, len(self.__outgoing) - 1)
				line = self.__outgoing.pop(index)
				
				# attach the prefix if we have to
				if self.__spam_prefix:
					reply = '%s %s' % (self.__spam_prefix, line)
				else:
					reply = line
				
				# spit it out
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
				
				tolog = "%s news item(s) remaining in outgoing queue" % len(self.__outgoing)
				self.putlog(LOG_DEBUG, tolog)
		
		# Once an hour, go and check for old news and purge it from the
		# db
		if currtime - self.__Last_Clearout_Time >= 3600:
			tolog = "Purging old news"
			self.putlog(LOG_DEBUG, tolog)
			
			self.__Last_Clearout_Time = currtime
			old_time = currtime - self.__old_threshold
			
			query = (TIME_QUERY, old_time)
			self.dbQuery(TIME_CHECK, query)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_URL(self, message):
		event, page_text = message.data
		
		# RSS feed
		if type(event) == types.TupleType:
			event, name = event
			self.__do_rss(page_text, event, name)
		
		else:
			if event.name in (NEWS_GOOGLE_WORLD, NEWS_GOOGLE_SCI, NEWS_GOOGLE_HEALTH,
				NEWS_GOOGLE_BIZ):
				
				parser = self.__google
			
			elif event.name == NEWS_ANANOVA:
				parser = self.__ananova
			
			else:
				errtext = "Unknown: %s" % event.name
				raise ValueError, errtext
			
			parser.reset_news()
			self.__do_news(page_text, parser, event)
	
	# -----------------------------------------------------------------------
	
	def __do_news(self, page_text, parser, event):
		try:
			parser.feed(page_text)
			parser.close()
		
		except HTMLParseError, e:
			# something fucked up
			tolog = "Error parsing news (%s) - %s" % (event.name, e)
			self.putlog(LOG_WARNING, tolog)
		
		else:
			articles = []
			queries = []
			for title in parser.news:
				#self.__to_process[title] = parser.news[title]
				
				#titles.append(title)
				#query = (NEWS_QUERY, title)
				#queries.append(query)
				
				articles.append((title, parser.news[title]))
				query = (NEWS_QUERY, title)
				queries.append(query)
			
			if queries:
				returnme = (event, articles)
				self.dbQuery(returnme, *queries)
	
	def __do_rss(self, page_text, event, name):
		feed = self.RSS_Feeds[name]
		
		#r = RSSParser()
		r = FeedParser()
		r.feed(page_text)
		
		if feed['title']:
			feed_title = feed['title']
		else:
			feed_title = r.channel.get('title', name)
		
		articles = []
		queries = []
		for item in r.items[:feed['maximum_new']]:
			item_title = '%s: %s' % (feed_title, item.get('title', '<No Title>'))
			
			if self.__rss_ignore_no_link:
				if not item.has_key('link'):
					tolog = "RSS item '%s' has no link!" % item_title
					self.putlog(LOG_DEBUG, tolog)
					continue
				link = item['link']
			else:
				link = item.get('link', '<no link>')
			
			desc = item.get('description', '')
			
			article = (item_title, (link, desc))
			articles.append(article)
			query = (NEWS_QUERY, item_title)
			queries.append(query)
		
		if queries:
			returnme = (event, articles)
			self.dbQuery(returnme, *queries)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		event, results = message.data
		if type(event) in (types.ListType, types.TupleType):
			event, articles = event
		
		if isinstance(event, PluginTimedEvent):
			# this wasn't a modification request
			currtime = time.time()
			queries = []
			
			for i in range(len(articles)):
				title, (url, description) = articles[i]
				result = results[i]
				
				# the title was in the news db, don't add it again
				if result:
					continue
				
				if self.__verbose and description:
					replytext = "%s - %s : %s" % (title, url, description)
				else:
					replytext = "%s - %s" % (title, url)
				
				reply = PluginReply(event, replytext)
				self.__outgoing.append(reply)
				
				# add it to the db!
				query = (INSERT_QUERY, title, url, description, currtime)
				queries.append(query)
			
			if queries:
				self.dbQuery(NEWS_INSERT, *queries)
				
				tolog = '%s: added %d items to outgoing queue' % (event.name, len(queries))
				self.putlog(LOG_DEBUG, tolog)
		
		elif isinstance(event, PluginTextTrigger):
			if event.name == NEWS_SEARCH:
				self.__news_search(event, results)
		
		elif event == NEWS_INSERT:
			# we just added some new items to our db
			pass
		
		elif event == TIME_CHECK:
			# we just did an hourly check for old news
			pass
		
		else:
			errtext = "Unknown event: %s" % event
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	
	# Search for a news article in our news db that matches the partial title
	# we were given by a user on irc
	def __news_search(self, trigger, results):
		search_text = trigger.match.group('search_text')
		if results == [()]:
			# the search failed
			replytext = "No headlines in the last %d days found matching '\02%s\02'" % (self.__old_days, search_text)
			self.sendReply(trigger, replytext)
		else:
			# check how many items we found
			results = results[0]
			if len(results) > MAX_NEWS_SEARCH_RESULTS:
				replytext = "Search for '\02%s\02' yielded too many results. Please refine your query." % search_text
				self.sendReply(trigger, replytext)
			
			elif len(results) > 1:
				# We found more than one and less than the max number of items
				replytext = "\02%d\02 Headlines found: " % len(results)
				while results:
					# can't use string.join() here :(
					replytext += "%s" % results[0]['title']
					results = results[1:]
					if results:
						replytext += " \02;;\02 "
				self.sendReply(trigger, replytext)
			
			else:
				# We found exactly one item, so reply with the headline and
				# url
				replytext = '%(title)s - %(url)s : %(description)s' % results[0]
				self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	# Pickle an object into the given file
	def __pickle(self, obj, filename):
		try:
			f = open(filename, "wb")
		except:
			# We couldn't open our file :(
			tolog = "Unable to open %s for writing" % filename
			self.putlog(LOG_WARNING, tolog)
		else:
			tolog = "saving pickle to %s" % filename
			self.putlog(LOG_DEBUG, tolog)
			# the 1 turns on binary-mode pickling
			cPickle.dump(obj, f, 1)
			f.flush()
			f.close()
	
	# -----------------------------------------------------------------------
	
	# Unpickle an object from the given file
	def __unpickle(self, filename):
		try:
			f = open(filename, "rb")
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			pass
		else:
			# We have a pickle!
			tolog = "loading pickle from %s" % filename
			self.putlog(LOG_DEBUG, tolog)
			obj = cPickle.load(f)
			f.close()
			return obj

# ---------------------------------------------------------------------------

# A parser for google's news pages. Looks for the main story titles.
class Google(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.reset_news()
	
	def reset_news(self):
		self.news = {}
		self.__temp_href = None
		self.__temp_title = None
		self.__found_a = 0
		self.__found_br1 = 0
		self.__found_br2 = 0
		self.reset()
	
	# -----------------------------------------------------------------------
	
	# Scan through the HTML, looking for a tag of the form <a class=y ..>
	def handle_starttag(self, tag, attributes):
		if tag == 'a':
			for attr, value in attributes:
				if attr == 'class' and value == 'y':
					# We have found a main headline
					self.__found_a = 1
				if self.__found_a and attr == 'href':
					# I'll just assume that q is always the last parameter for
					# now :p
					n = value.find('q=')
					if n >= 0:
						self.__temp_href = value[n+2:]
					else:
						self.__temp_href = value
					
					# fix up google's mangling of the url. this seems to be
					# causing breakage when following the links to some sites
					self.__temp_href = self.__temp_href.replace('%3F', '?')
					self.__temp_href = self.__temp_href.replace('%3D', '=')
					self.__temp_href = self.__temp_href.replace('%26', '&')
					self.__temp_href = self.__temp_href.replace('%25', '%')
		
		if self.__found_a and tag == 'br':
			if self.__found_br1:
				self.__found_br2 = 1
			else:
				self.__found_br1 = 1
	
	# -----------------------------------------------------------------------
	
	# Check to see if we have found a new headline, and if so, the data
	# between the <a ..> </a> tags is what we want to grab as the title.
	# Also, if we have found a headline, we check to see if we have found
	# two <br> tags, if so, the data between the second <br> and </br> is
	# our one-line summary of this article.
	def handle_data(self, data):
		if self.__found_a and not self.__found_br1:
			self.__temp_title = data
		elif self.__found_a and self.__found_br2:
			#item = "%s - %s" % (self.__temp_href, data)
			self.news[self.__temp_title] = (self.__temp_href, data)
			self.__found_a = 0
			self.__found_br1 = 0
			self.__found_br2 = 0

# ---------------------------------------------------------------------------

# A parser for ananov'a news pages. Looks for story titles?
class Ananova(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.reset_news()
	
	def reset_news(self):
		self.news = {}
		self.__found_a = 0
		self.__found_small = 0
		self.__temp_href = None
		self.__temp_title = None
		self.reset()
	
	def handle_starttag(self, tag, attributes):
		if tag == 'a':
			href = None
			title = None
			for attr, value in attributes:
				if attr == 'href' and value.startswith('./story'):
					# chop off the starting . and the ending ?menu=
					realvalue = value[1:-6]
					href = 'http://www.ananova.com/news' + realvalue
				elif attr == 'title':
					title = value
			
			if href and title:
				self.__temp_href = href
				self.__temp_title = title
				self.__found_a = 1
		
		elif self.__found_a and tag == 'small':
			self.__found_small = 1
	
	def handle_data(self, data):
		if self.__found_small:
			#item = "%s - %s" % (self.__temp_href, data)
			self.news[self.__temp_title] = (self.__temp_href, data)
			self.__found_a = 0
			self.__found_small = 0
