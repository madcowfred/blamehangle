# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it.
# exciting stuff.

from classes.Plugin import *
from classes.Constants import *

from classes.HTMLParser import HTMLParser, HTMLParseError
from random import Random
import cPickle, time

NEWS_GOOGLE_WORLD = "NEWS_CHECK_GOOGLE"
NEWS_GOOGLE_SCI = "NEWS_GOOGLE_SCI"
NEWS_ANANOVA = "NEWS_CHECK_ANANOVA"

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
INSERT_QUERY = "INSERT INTO news VALUES (%s,%s)"
TIME_QUERY = "DELETE FROM news WHERE time < %s"

# All this crap should be moved into the config, and then dealt with during
# setup()
GOOGLE_WORLD_TARGETS = {
						'GoonNET' : ['#grax'],
						'EFnet': ['#sausages']

				 		}
GOOGLE_SCI_TARGETS = {
						'GoonNET' : ['#grax'],
						'EFnet': ['#sausages']
						}
						
ANANOVA_TARGETS = {
	'GoonNET' : ['#grax'],
	'EFnet': ['#sausages']
}

GOOGLE_WORLD = 'http://news.google.com/news/gnworldleftnav.html'
GOOGLE_SCI = 'http://news.google.com/news/gntechnologyleftnav.html'
ANANOVA_QUIRK = 'http://www.ananova.com/news/index.html?keywords=Quirkies'


class News(Plugin):
	"""
	A news gatherer plugin.
	
	This will search for updated news stories on Google News and Ananova
	Quirkies (!), and reply with the title of and link to any that it finds.
	"""

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
		self.__anaq_targets = {}
		self.__setup_targets()

		self.__gwn_interval = self.Config.getint('News', 'google_world_interval')
		self.__gsci_interval = self.Config.getint('News', 'google_sci_interval')
		self.__anaq_interval = self.Config.getint('News', 'ananovaq_interval')
	
	# -----------------------------------------------------------------------

	def __setup_targets(self):
		for option in self.Config.options('News'):
			if option.startswith('google_world.'):
				network = option.split('.')[1]
				targets = self.Config.get('News', option).split()
				self.__gwn_targets[network] = targets
			elif option.startswith('google_sci.'):
				network = option.split('.')[1]
				targets = self.Config.get('News', option).split()
				self.__gsci_targets[network] = targets
			elif option.startswith('ananova.'):
				network = option.split('.')[1]
				targets = self.Config.get('News', option).split()
				self.__anaq_targets[network] = targets
	
	# -----------------------------------------------------------------------

	# Check google news every 5 minutes, and ananova every 6 hours
	def _message_PLUGIN_REGISTER(self, message):
		gwn = PluginTimedEvent(NEWS_GOOGLE_WORLD, self.__gwn_interval, self.__gwn_targets)
		gsci = PluginTimedEvent(NEWS_GOOGLE_SCI, self.__gsci_interval, self.__gsci_targets)
		anaq = PluginTimedEvent(NEWS_ANANOVA, self.__anaq_interval, self.__anaq_targets)

		self.register(gwn, gsci, anaq)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		event = message.data
		
		if event.name == NEWS_GOOGLE_WORLD:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_WORLD, event])
		elif event.name == NEWS_GOOGLE_SCI:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_SCI, event])
		elif event.name == NEWS_ANANOVA:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [ANANOVA_QUIRK, event])
		else:
			errstring = "News has no event: %s" % event.name
			raise ValueError, errstring
	
	# -----------------------------------------------------------------------

	def run_sometimes(self, currtime):
		# Periodically check if we need to send some text out to IRC
		if currtime - self.__Last_Spam_Time >= 30:
			self.__Last_Spam_Time = currtime
			if self.__outgoing:
				# We pull out a random item from our outgoing list so that
				# we don't end up posting slabs of stories from the same
				# site in a row
				index = self.__rand_gen.randint(0, len(self.__outgoing) - 1)
				reply = self.__outgoing.pop(index)
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
				

				tolog = "%s news items remaining in outgoing queue" % len(self.__outgoing)
				self.putlog(LOG_DEBUG, tolog)
			self.__pickle(self.__outgoing, '.news.out_pickle')
		
		# Once an hour, go and check for old news and purge it from the
		# db
		if currtime - self.__Last_Clearout_Time >= 3600:
			self.__Last_Clearout_Time = currtime
			two_days = 172800
			two_days_ago = currtime - two_days
			data = [(TIME_CHECK, None), (TIME_QUERY, [two_days_ago])]
			self.sendMessage('DataMonkey', REQ_QUERY, data)

	# -----------------------------------------------------------------------

	def _message_REPLY_URL(self, message):
		page_text, event = message.data

		if event.name == NEWS_GOOGLE_WORLD or event.name == NEWS_GOOGLE_SCI:
			parser = Google()
		elif event.name == NEWS_ANANOVA:
			parser = Ananova()
		else:
			errtext = "Unknown: %s" % event.name
			raise ValueError, errtext
			
		self.__do_news(page_text, parser, event)
	
	# -----------------------------------------------------------------------

	def __do_news(self, page_text, parser, event):
		try:
			parser.feed(page_text)
			parser.close()
		
		except HTMLParseError, e:
			# something fucked up
			tolog = "Error parsing news - %s" % e
			self.putlog(LOG_WARNING, tolog)
		
		else:
			for title in parser.news:
				data = [(event, title), (TITLE_QUERY, [title])]
				self.__to_process[title] = parser.news[title]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
				
				#if not title in store:
					## this is a new item!
					#store[title] = (parser.news[title], time.time())
					#replytext = "%s - %s" % (title, parser.news[title])
					#self.__outgoing.append(replytext)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_QUERY(self, message):
		result, (event, title) = message.data

		if isinstance(event, PluginTimedEvent):
			# this wasn't a modification request
			if result == [()]:
				# the title wasn't in the news db
				replytext = "%s - %s" % (title, self.__to_process[title])
				del self.__to_process[title]
				reply = PluginReply(event, replytext)
				self.__outgoing.append(reply)
				# add it to the db!
				data = [(TITLE_INSERT, title), (INSERT_QUERY, [title, time.time()])]
				self.sendMessage('DataMonkey', REQ_QUERY, data)
				
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

	# Upon shutdown, we need to save the news items we have seen, otherwise
	# the bot will spam every news story it sees when it is reloaded
	#def _message_REQ_SHUTDOWN(self, message):
	#	Plugin._message_REQ_SHUTDOWN(self, message)
	#	self.__pickles()

	# -----------------------------------------------------------------------
	
	def __pickles(self):
		self.__pickle(self.__google_world_news, '.news.gwn_pickle')
		self.__pickle(self.__google_sci_news, '.news.gsci_pickle')
		self.__pickle(self.__ananova_news, '.news.ana_pickle')
		self.__pickle(self.__outgoing, '.news.out_pickle')

	# -----------------------------------------------------------------------
	
	# Cache all the news we have discovered and the list of news yet to
	# announce on IRC, so that when the bot is restarted we can remember
	# all these values
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

	# Restore our cache of news titles we have found
	def __unpickle(self, pickle):
		try:
			f = open(pickle, "rb")
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			pass
		else:
			# We have a pickle!
			tolog = "trying to read pickle from %s" % pickle
			self.putlog(LOG_DEBUG, tolog)
			obj = cPickle.load(f)
			f.close()
			return obj
				
				
# ---------------------------------------------------------------------------

# A parser for google's news pages. Looks for the main story titles.
class Google(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		
		self.news = {}
	
	# If we come across an anchor tag, check to see if it has a "title"
	# attribute. If it does, we have found a news story.
	def handle_starttag(self, tag, attributes):
		if tag == 'a':
			href = None
			title = None
			for attr, value in attributes:
				if attr == 'href':
					href = value
				elif attr == 'title':
					title = value
			if title:
				self.news[title] = href

# ---------------------------------------------------------------------------

# A parser for ananov'a news pages. Looks for story titles?
class Ananova(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		
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
