# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Yahoo Sports game result lookup.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

SPORTS_SCORES = 'SPORTS_SCORES'
SCORES_HELP = '\02score\02 <league> <team> : Search for a score for <team> playing in <league> today. <league> can be one of NFL, MLB, NBA, NHL. <team> is identified by location, not nickname.'
SCORES_RE = re.compile(r'^score +(?P<league>NFL|MLB|NBA|NHL) +(?P<team>.+)$', re.I)
SCORES_URL = 'http://sports.yahoo.com/%s/'

SCORE_RE = re.compile(r'(\d+)<br>(\d+)')

# ---------------------------------------------------------------------------

class SportsFan(Plugin):
	"""
	"score <league> <team>"
	league can be one of: NFL, MLB, NBA, NHL
	team is identified by location, not nickname
	"""
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		self.setTextEvent(SPORTS_SCORES, SCORES_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('sports', 'score', SCORES_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Someone wants us to lookup a sports score
	def _trigger_SPORTS_SCORES(self, trigger):
		url = SCORES_URL % trigger.match.group('league').lower()
		self.urlRequest(trigger, self.__Parse_Scores, url)
	
	# -----------------------------------------------------------------------
	# We heard back from Yahoo. yay!
	def __Parse_Scores(self, trigger, page_text):
		team = trigger.match.group('team').lower()
		league = trigger.match.group('league').lower()
		
		# Find some score blocks
		chunks = FindChunks(page_text, '<td class="yspscores">', '</tr>')
		if not chunks:
			self.sendReply(trigger, 'Page parsing failed')
			return
		
		# See if any of them are for team scores
		teamlink = '/%s/teams/' % league
		for chunk in chunks:
			if chunk.find(teamlink) < 0:
				continue
			
			# Get our team names
			lines = StripHTML(chunk)
			
			away_team = lines[0].replace(' at', '')
			home_team = lines[1]
			
			# If it's the team we want, do some more stuff
			if away_team.lower() == team or home_team.lower() == team:
				# Find our score
				m = SCORE_RE.search(chunk)
				if not m:
					continue
				
				away_score = m.group(1)
				home_score = m.group(2)
				
				# See if it's a final score or not
				if lines[-1].startswith('Final'):
					thing = 'Final'
				else:
					thing = 'Progress'
				
				# Went to overtime?
				if lines[-1].endswith('OT'):
					replytext = '(%s score, overtime) %s %s - %s %s' % (thing, away_team, away_score, home_score, home_team)
				else:
					replytext = '(%s score) %s %s - %s %s' % (thing, away_team, away_score, home_score, home_team)
				
				self.sendReply(trigger, replytext)
				return
		
		# If we get here, we didn't find any matching games
		replytext = "Couldn't find a %s game for '%s'" % (league.upper(), team)
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
