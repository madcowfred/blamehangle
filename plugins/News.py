# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This is the news-gatherer plugin for Blamehangle. It scours the web for
# news, and reports it.
# exciting stuff.

from classes.Plugin import Plugin
from classes.Constans import *

from HTMLParser import HTMLParser

class News(Plugin):
	"""
	A news gatherer plugin.
	
	This will search for updated news stories on Google News and Ananova
	Quirkies (!), and reply with the title of and link to any that it finds.
	"""

	NEWS_GOOGLE_WORLD = "NEWS_CHECK_GOOGLE"
	NEWS_GOOGLE_SCI = "NEWS_GOOGLE_SCI"
	NEWS_ANANOVA = "NEWS_CHECK_ANANOVA"

	# All this crap should be moved into the config, and then dealt with during
	# setup()
	GOOGLE_WORLD_TARGETS = {
							'Goon' : ['#grax', 'zharradan'],
					 		'EFnet' : ['#sausages']
					 		}
	GOOGLE_SCI_TARGETS = {
							'Goon' : ['#grax', 'zharradan'],
							'EFnet' : ['#saussages']
							}
							
	ANANOVA_TARGETS = {'Goon' : ['#grax']}

	GOOGLE_WORLD = 'http://news.google.com/news/gnworldleftnav.html'
	GOOGLE_SCI = 'http://news.google.com/news/gntechnologyleftnav.html'

	def setup(self):
		self.__google_world_news = {}
		self.__google_sci_news = {}
		self.__ananova_news = {}
		
		# a list of all the news items we have found and want to send out to
		# irc
		self.__outgoing = []
		
	# -----------------------------------------------------------------------
	
	# Check google news every 4 minutes, and ananova every 6 hours
	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(TIMED, 2400, GOOGLE_WORLD_TARGETS, NEWS_GOOGLE_WORLD),
		(TIMED, 2400, GOOGLE_SCI_TARGETS, NEWS_GOOGLE_SCI),
		(TIMED, 18000, ANANOVA_TARGETS, NEWS_ANANOVA)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		targets, token, _, IRCtype, _, _ = message.data

		if token == NEWS_GOOGLE_WORLD:
			self.sendMessage('HTTPMonster', URL_REQ, [GOOGLE_WORLD, NEWS_GOOGLE_WORLD]
		elif token == NEWS_GOOGLE_SCI:
			self.sendMessage('HTTPMonster', URL_REQ, [GOOGLE_SCI, NEWS_GOOGLE_SCI]
		elif token == NEWS_ANANOVA:
			pass
		else:
			errstring = "News has no event: %s" % token
			raise ValueError, errstring
	
	# -----------------------------------------------------------------------

	# Periodically check if we need to send some text out to IRC
	def run_sometimes(self):
		if self.__outgoing:
			reply = self.__outgoing[0]
			self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
			del self.__outgoing[0]

	# -----------------------------------------------------------------------

	def _message_URL_REPLY(self, message):
		page_text, [targets, token, IRCtype] = message.data

		if token == NEWS_GOOGLE_WORLD:
			store = self.__google_world_news
			self.__do_google(page_text, store, targets, token, IRCtype)
		elif token == NEWS_GOOGLE_SCI:
			store = self.__google_sci_news
			self.__do_google(page_text, store, targets, token, IRCtype)
		elif token == NEWS_ANANOVA:
			self.__do_ananova(page_text, targets, token, IRCtype)
	
	# -----------------------------------------------------------------------

	def __do_google(self, page_text, store, targets, token, IRCtype):
		parser = Google()
		parser.feed(page_text)
		parser.close()

		for title in parser.news:
			if not title in store:
				# this is a new item!
				store[title] = parser.news[title]
				replytext = "%s - %s" % (title, parser.news[title])
				reply = [replytext, None, IRCtype, targets, None]
				self.__outgoing.append(reply)
	
	# -----------------------------------------------------------------------
	
	# haven't looked at ananova yet
	def __do_ananova(self, page_text, targets, token, IRCtype):
		pass

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
