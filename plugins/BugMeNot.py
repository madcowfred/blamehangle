# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Simple plugin to ask BugMeNot.com for login info.
"""

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

BUGMENOT_URL = 'http://www.bugmenot.com/view.php?url=%s'

# ---------------------------------------------------------------------------

class BugMeNot(Plugin):
	# Should probably cache results for a few hours, needs generic cache.
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_BugMeNot,
			regexp = re.compile(r'^bugmenot (\S+)$'),
			help = ('bugmenot', 'bugmenot', '\x02bugmenot\x02 <site> : See if BugMeNot has a login for <site>.'),
		)
	
	# -----------------------------------------------------------------------
	
	def __Fetch_BugMeNot(self, trigger):
		endbit = trigger.match.group(1)
		if len(endbit) < 5:
			self.sendReply(trigger, "Site must be at least 5 characters!")
		else:
			url = BUGMENOT_URL % QuoteURL(endbit)
			self.urlRequest(trigger, self.__Parse_BugMeNot, url)
	
	def __Parse_BugMeNot(self, trigger, resp):
		# No accounts
		if resp.data.find('No accounts found for ') >= 0:
			self.sendReply(trigger, "No accounts found.")
		
		# Result!
		elif resp.data.find('Login details for ') >= 0:
			# Find the site name
			forsite = FindChunk(resp.data, '<cite>', '</cite>')
			if forsite is None:
				self.sendReply(trigger, "Page parsing failed: cite.")
				return
			
			# Find the login info
			login = FindChunk(resp.data, '<dd>', '</dd>')
			if login is None:
				self.sendReply(trigger, "Page parsing failed: dd.")
				return
			
			# See if we got the right bits
			parts = login.split('<br />')
			if len(parts) != 2:
				self.sendReply(trigger, "Page parsing failed: login.")
				return
			
			# All done, build the reply and send it
			replytext = 'Login info for %s \x02::\x02 %s \x02/\x02 %s' % (forsite, parts[0], parts[1])
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
