# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Miscellaneous stuff that doesn't really deserve it's own plugin.
"""

import re
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

BUGMENOT_URL = 'http://www.bugmenot.com/view.php?url=%s'
PGP_URL = "http://pgp.mit.edu:11371/pks/lookup?op=index&search=%s"

# ---------------------------------------------------------------------------

class Misc(Plugin):
	_HelpSection = 'misc'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_BugMeNot,
			regexp = re.compile(r'^bugmenot (\S+)$'),
			help = ('bugmenot', '\x02bugmenot\x02 <site> : See if BugMeNot has a login for <site>.'),
		)
		self.addTextEvent(
			method = self.__Fetch_PGP_Key,
			regexp = re.compile(r'^pgpkey (\S+)$'),
			help = ('pgpkey', '\x02pgpkey\x02 <findme> : Search pgp.mit.edu for a key/keys matching <findme>, returning the first match.'),
		)
	
	# -----------------------------------------------------------------------
	# Fetch the search results.
	def __Fetch_BugMeNot(self, trigger):
		endbit = trigger.match.group(1)
		if len(endbit) < 5:
			self.sendReply(trigger, "Site must be at least 5 characters!")
		else:
			url = BUGMENOT_URL % QuoteURL(endbit)
			self.urlRequest(trigger, self.__Parse_BugMeNot, url)
	
	# Parse the returned page.
	def __Parse_BugMeNot(self, trigger, resp):
		# No accounts
		if resp.data.find('"add.php?notFound=true') >= 0:
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
		
		# Err?
		else:
			self.sendReply(trigger, "Failed to parse page!")
	
	# -----------------------------------------------------------------------
	# Fetch the search results.
	def __Fetch_PGP_Key(self, trigger):
		url = PGP_URL % (QuoteURL(trigger.match.group(1)))
		self.urlRequest(trigger, self.__Parse_PGP_Key, url)
	
	# Parse the returned page.
	_parse_re = re.compile(r'(\d+)(.)\/<a href="(.*?)">[A-Z0-9]+</a> (\d\d\d\d\/\d\d\/\d\d) (.*?) \&lt;<a href=".*?">(.*?)</a>')
	def __Parse_PGP_Key(self, trigger, resp):
		findme = trigger.match.group(1)
		
		# No results
		if resp.data.find('No matching keys') >= 0:
			replytext = "No keys found matching '%s'." % (findme)
			self.sendReply(trigger, replytext)
			return
		
		# Too many results
		if resp.data.find('exceeded maximum allowed') >= 0:
			self.sendReply(trigger, "Too many results returned! Try to narrow down your search string.")
			return
		
		# See what we got
		chunks = FindChunks(resp.data, 'pub', '&gt;')
		if not chunks:
			self.sendReply(trigger, "Page parsing failed: key search.")
			return
		
		# Off we go
		first = None
		for m in [self._parse_re.search(chunk) for chunk in chunks]:
			if m:
				bits, typ, getlink, date, name, email = m.groups()
				
				done = 0
				if '@' in findme:
					if not first:
						first = (name, email, bits, typ, date, urlparse.urljoin(PGP_URL, getlink))
					if email == findme:
						done = 1
				else:
					done = 1
				
				if done:
					geturl = urlparse.urljoin(PGP_URL, getlink)
					
					replytext = "PGP key for '%s' (%s): %sbit %sSA, added %s - %s" % (
						name, email, bits, typ, date, geturl)
					self.sendReply(trigger, replytext)
					return
		
		# Nothing matched here. If we got at least one match, spit it out instead.
		if first:
			replytext = "No exact match! PGP key for '%s' (%s): %sbit %sSA, added %s - %s" % first
			self.sendReply(trigger, replytext)
		
		else:
			self.sendReply(trigger, "No matches found, page might have changed!")

# ---------------------------------------------------------------------------
