# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it.
# exciting stuff.

from random import Random
import cPickle
import re
import time
import types

from classes.Constants import *
from classes.Plugin import *
from classes.rssparser import RSSParser

from classes.HTMLParser import HTMLParser, HTMLParseError

# ---------------------------------------------------------------------------

NEWS_GOOGLE_WORLD = "NEWS_CHECK_GOOGLE"
NEWS_GOOGLE_SCI = "NEWS_GOOGLE_SCI"
NEWS_GOOGLE_HEALTH = "NEWS_GOOGLE_HEALTH"
NEWS_GOOGLE_BIZ = "NEWS_GOOGLE_BIZ"
NEWS_ANANOVA = "NEWS_CHECK_ANANOVA"

NEWS_RSS = "NEWS_RSS"

TITLE_INSERT = "TITLE_INSERT"
TIME_CHECK = "TIME_CHECK"

# I tried using "datetime" as the type for the time column, but it created
# interesting things like the following:
#+-------+---------------------+
#| title | time                |
#+-------+---------------------+
#| hello | 2000-10-47 63:46:97 |
#+-------+---------------------+
# so I for the following
#CREATE TABLE news (
#	title varchar(255) NOT NULL default '',
#	time bigint UNSIGNED default NULL,
#	PRIMARY KEY (title)
#	TYPE=MyISAM;


TITLE_QUERY = "SELECT title FROM news WHERE title = %s"
INSERT_QUERY = "INSERT INTO news (title, time) VALUES (%s,%s)"
TIME_QUERY = "DELETE FROM news WHERE time < %s"


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
	
	RSS_Feeds = {}
	
	def setup(self):
		self.__outgoing = self.__unpickle('.news.out_pickle') or []
		
		self.__to_process = {}
		
		self.__Last_Spam_Time = time.time()
		self.__Last_Clearout_Time = time.time()
		
		self.__rand_gen = Random(time.time())
		
		self.__spam_delay = self.Config.getint('News', 'spam_delay')
		
		old_days = self.Config.getint('News', 'old_threshold')
		self.__old_threshold = old_days * 86400
		
		self.__gwn_targets = {}
		self.__gsci_targets = {}
		self.__gh_targets = {}
		self.__gbiz_targets = {}
		self.__anaq_targets = {}
		self.__setup_targets()
		
		if self.Config.getboolean('News', 'verbose'):
			tolog = "Using verbose mode for news"
			self.__google = GoogleVerbose()
			self.__ananova = AnanovaVerbose()
		else:
			tolog = "Using brief mode for news"
			self.__google = GoogleBrief()
			self.__ananova = AnanovaBrief()
		self.putlog(LOG_DEBUG, tolog)
		
		
		self.__gwn_interval = self.Config.getint('News', 'google_world_interval')
		self.__gsci_interval = self.Config.getint('News', 'google_sci_interval')
		self.__gh_interval = self.Config.getint('News', 'google_health_interval')
		self.__gbiz_interval = self.Config.getint('News', 'google_business_interval')
		self.__anaq_interval = self.Config.getint('News', 'ananovaq_interval')
		
		# Do RSS feed setup
		self.__rss_interval = self.Config.getint('RSS', 'interval') * 60
		
		self.__Setup_RSS_Feeds()
	
	# -----------------------------------------------------------------------
	
	def __setup_targets(self):
		for option in self.Config.options('News'):
			if option.startswith('google_world.'):
				self.__setup_target(self.__gwn_targets, option)
			elif option.startswith('google_sci.'):
				self.__setup_target(self.__gsci_targets, option)
			elif option.startswith('google_health.'):
				self.__setup_target(self.__gh_targets, option)
			elif option.startswith('google_business.'):
				self.__setup_target(self.__gbiz_targets, option)
			elif option.startswith('ananova.'):
				self.__setup_target(self.__anaq_targets, option)
	
	def __setup_target(self, target_store, option):
		network = option.split('.')[1]
		targets = self.Config.get('News', option).split()
		target_store[network] = targets
	
	# -----------------------------------------------------------------------
	# Do stuff
	def __Setup_RSS_Feeds(self):
		for section in self.Config.sections():
			if not section.startswith('RSS.'):
				continue
			
			name = section.split('.', 1)[1]
			
			feed = {}
			
			if self.Config.has_option(section, 'title'):
				feed['title'] = self.Config.get(section, 'title')
			else:
				feed['title'] = None
			
			if self.Config.has_option(section, 'interval'):
				feed['interval'] = self.Config.getint(section, 'interval') * 60
			else:
				feed['interval'] = self.__rss_interval
			
			feed['url'] = self.Config.get(section, 'url')
			
			self.RSS_Feeds[name] = feed
	
	# -----------------------------------------------------------------------
	
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
		
		for name in self.RSS_Feeds:
			feed = self.RSS_Feeds[name]
			
			tolog = 'Registering RSS feed %s: %s' % (name, feed['url'])
			self.putlog(LOG_DEBUG, tolog)
			
			event = PluginTimedEvent(NEWS_RSS, feed['interval'], {'GoonNET':['#grax']}, name)
			self.register(event)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		event = message.data
		
		if event.name == NEWS_GOOGLE_WORLD:
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_WORLD, event])
		elif event.name == NEWS_GOOGLE_SCI:
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_SCI, event])
		elif event.name == NEWS_GOOGLE_HEALTH:
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_HEALTH, event])
		elif event.name == NEWS_GOOGLE_BIZ:
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_BIZ, event])
		elif event.name == NEWS_ANANOVA:
			self.sendMessage('HTTPMonster', REQ_URL, [ANANOVA_QUIRK, event])
		elif event.name == NEWS_RSS:
			name = event.args[0]
			feed = self.RSS_Feeds[name]
			data = [feed['url'], (event, name)]
			self.sendMessage('HTTPMonster', REQ_URL, data)
		else:
			errstring = "News has no event: %s" % event.name
			raise ValueError, errstring
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		# Periodically check if we need to send some text out to IRC
		if currtime - self.__Last_Spam_Time >= self.__spam_delay:
			self.__Last_Spam_Time = currtime
			if self.__outgoing:
				# We pull out a random item from our outgoing list so that
				# we don't end up posting slabs of stories from the same
				# site in a row
				index = self.__rand_gen.randint(0, len(self.__outgoing) - 1)
				reply = self.__outgoing.pop(index)
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
				

				tolog = "%s news item(s) remaining in outgoing queue" % len(self.__outgoing)
				self.putlog(LOG_DEBUG, tolog)
			self.__pickle(self.__outgoing, '.news.out_pickle')
		
		# Once an hour, go and check for old news and purge it from the
		# db
		if currtime - self.__Last_Clearout_Time >= 3600:
			tolog = "Purging old news"
			self.putlog(LOG_DEBUG, tolog)
			
			self.__Last_Clearout_Time = currtime
			old_time = currtime - self.__old_threshold
			
			query = (TIME_QUERY, old_time)
			self.dbQuery(TIME_CHECK, query)
			#data = [(TIME_CHECK, None), (TIME_QUERY, [old_time])]
			#self.sendMessage('DataMonkey', REQ_QUERY, data)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_URL(self, message):
		page_text, event = message.data
		
		# RSS feed
		if type(event) == types.TupleType:
			event, name = event
			self.__do_rss(page_text, event, name)
		
		else:
			if event.name == NEWS_GOOGLE_WORLD or event.name == NEWS_GOOGLE_SCI \
				or event.name == NEWS_GOOGLE_HEALTH or event.name == NEWS_GOOGLE_BIZ:
				
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
			titles = []
			queries = []
			for title in parser.news:
				self.__to_process[title] = parser.news[title]
				
				titles.append(title)
				query = (TITLE_QUERY, title)
				queries.append(query)
			
			if queries:
				returnme = (event, titles)
				self.dbQuery(returnme, *queries)
	
	def __do_rss(self, page_text, event, name):
		feed = self.RSS_Feeds[name]
		
		r = RSSParser()
		r.feed(page_text)
		
		if feed['title']:
			feed_title = feed['title']
		else:
			feed_title = r.channel['title']
		
		titles = []
		queries = []
		for item in r.items:
			title = '%s: %s' % (feed_title, item['title'])
			self.__to_process[title] = item['link']
			
			titles.append(title)
			query = (TITLE_QUERY, title)
			queries.append(query)
		
		if queries:
			returnme = (event, titles)
			self.dbQuery(returnme, *queries)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		event, results = message.data
		if type(event) in (types.ListType, types.TupleType):
			event, titles = event
		
		if isinstance(event, PluginTimedEvent):
			# this wasn't a modification request
			currtime = time.time()
			queries = []
			
			for i in range(len(titles)):
				title = titles[i]
				result = results[i]
				
				# the title was in the news db, don't add it again
				if result:
					continue
				
				replytext = "%s - %s" % (title, self.__to_process[title])
				del self.__to_process[title]
				
				reply = PluginReply(event, replytext)
				self.__outgoing.append(reply)
				
				# add it to the db!
				query = (INSERT_QUERY, title, currtime)
				queries.append(query)
			
			if queries:
				self.dbQuery(TITLE_INSERT, *queries)
		
		elif event == TITLE_INSERT:
			# we just added a new item to our db
			pass
		
		elif event == TIME_CHECK:
			# we just did an hourly check for old news
			pass
		
		else:
			errtext = "Unknown event: %s" % event
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	
	# Pickle an object into the given file
	def __pickle(self, obj, pickle):
		try:
			f = open(pickle, "wb")
		except:
			# We couldn't open our file :(
			tolog = "Unable to open %s for writing" % filename
			self.putlog(LOG_WARNING, tolog)
		else:
			# the 1 turns on binary-mode pickling
			cPickle.dump(obj, f, 1)
			f.flush()
			f.close()
	
	# -----------------------------------------------------------------------
	
	# Unpickle an object from the given file
	def __unpickle(self, pickle):
		try:
			f = open(pickle, "rb")
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			pass
		else:
			# We have a pickle!
			tolog = "loading pickle from %s" % pickle
			self.putlog(LOG_DEBUG, tolog)
			obj = cPickle.load(f)
			f.close()
			return obj

# ---------------------------------------------------------------------------

# A parser for google's news pages. Looks for the main story titles.
# Produces brief output: "headline - URL"
class GoogleBrief(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.reset_news()
	
	def reset_news(self):
		self.news = {}
		self.__temp_href = None
		self.__found = 0
	
	# Scan through the HTML, looking for a tag of the form <a class=y ..>
	def handle_starttag(self, tag, attributes):
		if tag == 'a':
			for attr, value in attributes:
				if attr == 'class' and value == 'y':
					# We have found a main headline
					self.__found = 1
				if self.__found and attr == 'href':
					self.__temp_href = value
	
	# Check to see if we have found a new headline, and if so, the data
	# between the <a ..> </a> tags is what we want to grab as the title.
	def handle_data(self, data):
		if self.__found:
			self.news[data] = self.__temp_href
			self.__found = 0
			self.__temp_href = None

# ---------------------------------------------------------------------------

# A parser for google's news pages. Looks for the main story titles.
# Produces verbose output: "headline - URL - summary"
class GoogleVerbose(HTMLParser):
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
		
	# -----------------------------------------------------------------------
	
	# Scan through the HTML, looking for a tag of the form <a class=y ..>
	def handle_starttag(self, tag, attributes):
		if tag == 'a':
			for attr, value in attributes:
				if attr == 'class' and value == 'y':
					# We have found a main headline
					self.__found_a = 1
				if self.__found_a and attr == 'href':
					self.__temp_href = value

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
			item = "%s - %s" % (self.__temp_href, data)
			self.news[self.__temp_title] = item
			self.__found_a = 0
			self.__found_br1 = 0
			self.__found_br2 = 0
			
## ---------------------------------------------------------------------------

# A parser for ananov'a news pages. Looks for story titles?
class AnanovaBrief(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.reset_news()

	def reset_news(self):
		self.news = {}
	
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
				self.news[title] = href
# ---------------------------------------------------------------------------

# A parser for ananov'a news pages. Looks for story titles?
class AnanovaVerbose(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.reset_news()

	def reset_news(self):
		self.news = {}
		self.__found_a = 0
		self.__found_small = 0
		self.__temp_href = None
		self.__temp_title = None
	
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
			item = "%s - %s" % (self.__temp_href, data)
			self.news[self.__temp_title] = item
			self.__found_a = 0
			self.__found_small = 0
