# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Yahoo Sports game result lookup

import re

from classes.Plugin import *
from classes.Constants import *

# ---------------------------------------------------------------------------

SCORES = "SCORES"
SCORES_RE = re.compile("^score\s+(?P<league>NFL|MLB|NBA|NHL)\s+(?P<team>.+)$", re.I)

# ---------------------------------------------------------------------------

class SportsFan(Plugin):
	"""
	"score <league> <team>"
	league can be one of: NFL, MLB, NBA, NHL
	team is identified by location, not nickname
	"""
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		scores_dir = PluginTextEvent(SCORES, IRCT_PUBLIC_D, SCORES_RE)
		scores_msg = PluginTextEvent(SCORES, IRCT_MSG, SCORES_RE)
		
		self.register(scores_dir, scores_msg)
		self.__set_help_msgs()
	
	def __set_help_msgs(self):
		SCORES_HELP = "'\02score\02 <league> <team>' : Search for a score for <team> playing in <league> today. <league> can be one of NFL, MLB, NBA, NHL. <team> is identified by location, not nickname."
		
		self.setHelp('sports', 'score', SCORES_HELP)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == SCORES:
			self.__scores(trigger)
		else:
			errtext = "SportsFan got a bad event: %s" % trigger.name
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	
	# Someone wants us to lookup a sports score
	def __scores(self, trigger):
		url = "http://sports.yahoo.com/%s/" % trigger.match.group('league').lower()
		self.urlRequest(trigger, url)
	
	# -----------------------------------------------------------------------
	
	# We heard back from Yahoo. yay!
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		team = trigger.match.group('team')
		league = trigger.match.group('league')
		
		# Search for our info in the page Yahoo Sports gave us
		find_re = re.compile(r'^\s*<a href="/%s/teams/.*?at<br>$' % league, re.I)
		
		lines = page_text.splitlines()
		for i in range(len(lines)):
			line = lines[i]
			if find_re.match(line):
				# We found the away team in this game
				away = self.__parse(line)[:-3]
				
				# the next line is the home team
				home = self.__parse(lines[i+1])
				
				# one line of crappy html, then the scores
				away_score, home_score = self.__find_scores(lines[i+3])
				
				# this line indicates if this is a final score or not
				blah = self.__parse(lines[i+7])
				if blah == "Final":
					game_status = "(Final score)"
				else:
					game_status = "(Progress score)"
				
				tolog = "Found a game: %s %s: %s - %s: %s" % (game_status, home, home_score, away, away_score)
				self.putlog(LOG_DEBUG, tolog)
				
				# check to see if this is the game the user was asking about
				if team.lower() == away.lower() or team.lower() == home.lower():
					replytext = '%s %s: %s - %s: %s' % (game_status, home, home_score, away, away_score)
					self.sendReply(trigger, replytext)
					return
		
		# If we get here, we didn't find any games that matched what the user
		# was looking for
		replytext = "Couldn't find a %s game today for '%s'" % (league, team)
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# remove all the HTML tags and the trailing newline from the supplied line
	def __parse(self, text):
		text = re.sub("<.+?>", "", text)
		text = text.replace("&nbsp;", " ")
		if text.endswith("\n"):
			text = text[:-1]
		return text.strip()
	
	# -----------------------------------------------------------------------
	# Find the scores in the current line
	def __find_scores(self, text):
		text = text.replace("<", " <")
		text = self.__parse(text)
		
		foo = text.split()
		if len(foo) == 2:
			return foo
		else:
			return (-1, -1)
