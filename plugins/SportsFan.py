# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
FIXME: parsing is broken, either fix or find decent pages to use!
"""

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

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
	
	def register(self):
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
	def __Parse_Scores(self, trigger, resp):
		team = trigger.match.group('team').lower()
		league = trigger.match.group('league').lower()
		
		# Find some score blocks
		chunks = FindChunks(resp.data, '<td class="yspscores">', '</tr>')
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
