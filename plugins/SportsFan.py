# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Yahoo Sports game result lookup

from classes.Plugin import *
from classes.Constants import *

import re, cStringIO

SCORES = "SCORES"

s0 = "^score +"
s1 = "(?P<league>(NFL|MLB|NBA|NCAAF|NCAAB|NCAAW|NHL)) +"
s2 = "(?P<team>.+)$"

SCORES_RE = re.compile(s0+s1+s2)

class SportsFan(Plugin):
	"""
	"score <league> <team>"
	league can be one of: NFL, MLB, NCAAF, NCAAB, NCAAW, NHL
	team is identified by location, not nickname
	"""

	# -----------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		scores_dir = PluginTextEvent(SCORES, IRCT_PUBLIC_D, SCORES_RE)
		scores_msg = PluginTextEvent(SCORES, IRCT_MSG, SCORES_RE)

		self.register(scores_dir, scores_msg)
	
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
		league = trigger.match.group('league').lower()
		url = "http://sports.yahoo.com/" + league + "/"

		self.sendMessage('HTTPMonster', REQ_URL, [url, trigger])
	
	# -----------------------------------------------------------------------

	# We heard back from Yahoo. yay!
	def _message_REPLY_URL(self, message):
		page_text, trigger = message.data
		team = trigger.match.group('team')
		league = trigger.match.group('league')

		# Search for our info in the page Yahoo Sports gave us
		s = cStringIO.StringIO(page_text)
		
		line = s.readline()
		while line:
			line = line.strip()
			if line.startswith('<a href="/%s/teams/' % league.lower()) \
			and line.endswith("at<br>"):
				# We found the away team in this game
				away = self.__parse(line)[:-3]
				
				# the next line is the home team
				line = s.readline()
				home = self.__parse(line)

				# there are two lines with only html in them that follow
				line = s.readline()
				line = s.readline()

				# the next line has the scores
				line = s.readline()
				away_score, home_score = self.__find_scores(line)

				# the next 3 lines contain nothing interesting
				line = s.readline()
				line = s.readline()
				line = s.readline()

				# the next line indicates if this is a final score or not
				line = s.readline()
				line = self.__parse(line)
				if line == "Final":
					game_status = "(Final score)"
				else:
					game_status = "(Progress score)"

				tolog = "Found a game: %s %s: %s - %s: %s" % (game_status, home, home_score, away, away_score)
				self.putlog(LOG_DEBUG, tolog)

				# check to see if this is the game the user was asking about
				if team.lower() == away.lower() or team.lower() == home.lower():
					replytext = "%s " % game_status
					replytext += "%s: %s - " % (home, home_score)
					replytext += "%s: %s" % (away, away_score)
					self.sendReply(trigger, replytext)
					return
			
			# Keep looping, looking for games
			line = s.readline()

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
		return text.split()
