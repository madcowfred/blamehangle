# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it.
# exciting stuff.

from classes.Plugin import Plugin
from classes.Constants import *

from classes.HTMLParser import HTMLParser, HTMLParseError
from random import Random
import cPickle, time

NEWS_GOOGLE_WORLD = "NEWS_CHECK_GOOGLE"
NEWS_GOOGLE_SCI = "NEWS_GOOGLE_SCI"
NEWS_ANANOVA = "NEWS_CHECK_ANANOVA"

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
		# The pickle dir should probably come from the config, also
		self.pickle_dir = '.pickles/'
		
		self.__google_world_news = self.__unpickle('.news.gwn_pickle') or {}
		self.__google_sci_news = self.__unpickle('.news.gsci_pickle') or {}
		self.__ananova_news = self.__unpickle('.news.ana_pickle') or {}
		self.__outgoing = self.__unpickle('.news.out_pickle') or []
		
		self.__Last_Spam_Time = time.time()
		self.__Last_Clearout_Time = time.time()

		self.__rand_gen = Random(time.time())
		
	
	# -----------------------------------------------------------------------

	# Check google news every 5 minutes, and ananova every 6 hours
	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(IRCT_TIMED, 300, GOOGLE_WORLD_TARGETS, NEWS_GOOGLE_WORLD),
		(IRCT_TIMED, 1800, GOOGLE_SCI_TARGETS, NEWS_GOOGLE_SCI),
		(IRCT_TIMED, 3600, ANANOVA_TARGETS, NEWS_ANANOVA)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		targets, token, _, IRCtype, _, _ = message.data

		if token == NEWS_GOOGLE_WORLD:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_WORLD, [targets, token, IRCtype]])
		elif token == NEWS_GOOGLE_SCI:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [GOOGLE_SCI, [targets, token, IRCtype]])
		elif token == NEWS_ANANOVA:
			#pass
			self.sendMessage('HTTPMonster', REQ_URL, [ANANOVA_QUIRK, [targets, token, IRCtype]])
		else:
			errstring = "News has no event: %s" % token
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

			# This is also an appropriate place to check to see if any news
			# items in our various stores are old and need to be purged
			# (we purge old items so that these data structures do not
			# bloat into crazy oblivion)
			for store in [
				self.__google_world_news,
				self.__google_sci_news,
				self.__ananova_news
				]:
			
				for title in store:
					url, post_time = store[title]
					# 60 sec * 60 min * 24 hour * 2 day = 172800
					if currtime - post_time > 172800:
						del store[title]
			
			self.__pickles()


	# -----------------------------------------------------------------------

	def _message_REPLY_URL(self, message):
		page_text, [targets, token, IRCtype] = message.data

		if token == NEWS_GOOGLE_WORLD:
			store = self.__google_world_news
			self.__do_google(page_text, store, targets, token, IRCtype)
		elif token == NEWS_GOOGLE_SCI:
			store = self.__google_sci_news
			self.__do_google(page_text, store, targets, token, IRCtype)
		elif token == NEWS_ANANOVA:
			store = self.__ananova_news
			self.__do_ananova(page_text, store, targets, token, IRCtype)
	
	# -----------------------------------------------------------------------

	def __do_google(self, page_text, store, targets, token, IRCtype):
		parser = Google()
		try:
			parser.feed(page_text)
			parser.close()
		
		except HTMLParseError, e:
			# something fucked up
			tolog = "Error parsing google - %s" % e
			self.putlog(LOG_WARNING, tolog)
		
		else:
			for title in parser.news:
				if not title in store:
					# this is a new item!
					store[title] = (parser.news[title], time.time())
					replytext = "%s - %s" % (title, parser.news[title])
					reply = [replytext, None, IRCtype, targets, None]
					self.__outgoing.append(reply)
	
	# -----------------------------------------------------------------------
	
	# haven't looked at ananova yet
	def __do_ananova(self, page_text, store, targets, token, IRCtype):
		parser = Ananova()
		try:
			parser.feed(page_text)
			parser.close()

		except HTMLParseError, e:
			tolog = "Error parsing ananova - %s" % e
			self.putlog(LOG_WARNING, tolog)
		
		else:
			for title in parser.news:
				if not title in store:
					# this is a new item!
					store[title] = (parser.news[title], time.time())
					replytext = "%s - %s" % (title, parser.news[title])
					reply = [replytext, None, IRCtype, targets, None]
					self.__outgoing.append(reply)
	
	# -----------------------------------------------------------------------

	# Upon shutdown, we need to save the news items we have seen, otherwise
	# the bot will spam every news story it sees when it is reloaded
	def _message_REQ_SHUTDOWN(self, message):
		Plugin._message_REQ_SHUTDOWN(self, message)
		self.__pickles()

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
		filename = self.pickle_dir + pickle
		try:
			f = open(filename, "wb")
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
		filename = self.pickle_dir + pickle
		try:
			f = open(filename, "rb")
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			pass
		else:
			# We have a pickle!
			tolog = "trying to read pickle from %s" % filename
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
