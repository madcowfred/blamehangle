# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004, MadCowDisease
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
Miscellaneous stuff that doesn't really deserve it's own plugin.
"""

import re
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

BUGMENOT_URL = 'http://www.bugmenot.com/view.php?url=%s'
FEDEX_URL = "http://www.fedex.com/cgi-bin/tracking?action=track&language=english&ascend_header=1&cntry_code=us&initial=x&mps=y&tracknumbers=%s"
#FEDEX_URL = "http://fridge/~freddie/tracking.html?%s"
PGP_URL = "http://pgp.mit.edu:11371/pks/lookup?op=index&search=%s"

SPACE_RE = re.compile('\s+')

# ---------------------------------------------------------------------------

class Misc(Plugin):
	_HelpSection = 'misc'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_BugMeNot,
			regexp = r'^bugmenot (\S+)$',
			help = ('bugmenot', '\x02bugmenot\x02 <site> : See if BugMeNot has a login for <site>.'),
		)
		self.addTextEvent(
			method = self.__Fetch_FedEx,
			regexp = r'^fedex (\d+)$',
			help = ('fedex', '\x02fedex\x02 <tracking number> : Get some info about a FedEx package.'),
		)
		self.addTextEvent(
			method = self.__Fetch_PGP_Key,
			regexp = r'^pgpkey (\S+)$',
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
	# Fetch the package info
	def __Fetch_FedEx(self, trigger):
		url = FEDEX_URL % (trigger.match.group(1))
		self.urlRequest(trigger, self.__Parse_FedEx, url)
	
	# Parse the page
	def __Parse_FedEx(self, trigger, resp):
		# Errorrrrr
		if 'Please check the following numbers and resubmit.' in resp.data:
			self.sendReply(trigger, 'Invalid tracking number!')
			return
		if 'No scan record for the following shipments has been received' in resp.data:
			self.sendReply(trigger, 'Shipment has not been scanned yet!')
			return
		
		# Find the shipment info
		chunk = FindChunk(resp.data, '<!-- shipment info -->', '<!-- shipment tracking stats -->')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: shipment info.')
			return
		
		trs = FindChunks(chunk, '<tr valign="top" bgcolor="#E6E6E6">', '</tr>')
		if not trs:
			self.sendReply(trigger, 'Page parsing failed: shipment info trs.')
			return
		
		# Not delivered yet?
		if len(trs) == 8:
			checkme = (7, 6, 2, 3)
		# Delivered already?
		elif len(trs) == 10:
			checkme = (9, 8, 7, 2, 3, 4)
		# No idea
		else:
			self.sendReply(trigger, 'Page parsing failed: shipment info tr count.')
			return
		
		parts = []
		for i in checkme:
			tds = FindChunks(trs[i], '<td>', '</td>')
			if not tds:
				continue
			
			thing = FindChunk(tds[0], '<b>', '</b>')
			value = SPACE_RE.sub(' ', tds[-1])
			
			if thing and value:
				part = '%s: %s' % (thing, value)
				parts.append(part)
		
		if not parts:
			self.sendReply(trigger, 'Page parsing failed: no parts?')
			return
		
		# Find the scan activity
		chunk = FindChunk(resp.data, '<!-- BEGIN Scan Activity -->', '<!-- END Scan Activity -->')
		if chunk:
			trs = FindChunks(resp.data, '<tr bgcolor="#E6E6E6">', '</tr>')
			if trs:
				tds = FindChunks(trs[0], '<td', '</td>')
				if len(tds) == 16:
					shipdate = StripHTML(tds[1])[0]
					shiptime = StripHTML(tds[2])[0]
					shipthing = StripHTML(tds[6])[0]
					shiploc = StripHTML(tds[10])[0]
					
					part = 'Last update: %s %s - %s %s' % (shipdate, shiptime, shipthing, shiploc)
					parts.append(part)
					
					comment = StripHTML(tds[14])
					if comment:
						part = 'Comment: %s' % (comment[0])
						parts.append(part)
		
		# Spit it out
		replytext = ' '.join(['\x02[\x02%s\x02]\x02' % part for part in parts])
		self.sendReply(trigger, replytext)
	
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
