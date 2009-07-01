# Copyright (c) 2003-2009, blamehangle team
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
Downloads NZB files and sticks them in a configured directory.
"""

import os
import re
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

DNZB_URL = 'http://v3.newzbin.com/api/dnzb/'
NEWZBIN_URL_RE = re.compile(r'^http://(?:www|v3).newzbin.com/browse/post/(\d+)/?$')

NEWZLEECH_GET_URL = 'http://www.newzleech.com/?m=gen'
NEWZLEECH_URL_RE = re.compile(r'^http://(?:www\.|)newzleech\.com/(?:posts/|)\?p=(\d+).*$')

CD_FILENAME_RE = re.compile('filename=([^;]+)')

# ---------------------------------------------------------------------------

class GrabNZB(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('GrabNZB', autosplit=True)
		
		# Compile our regexps
		self.__grab_res = []
		for regexp in self.OptionsList('GrabNZB-Allowed'):
			try:
				r = re.compile(regexp)
			except Exception, msg:
				tolog = "Failed to compile regexp '%s': %s" % (regexp, msg)
				self.putlog(LOG_WARNING, tolog)
			else:
				self.__grab_res.append(r)
		
		if not self.Options['commands'] and not self.Options['newfiles']:
			self.putlog(LOG_WARNING, "GrabBT has no channels configured!")
	
	def register(self):
		self.addTextEvent(
			method = self.__NZB_Grab,
			regexp = r'^grabnzb (.+)$',
			IRCTypes = (IRCT_PUBLIC_D,),
		)
	
	# -----------------------------------------------------------------------
	# Do the heavy lifting
	def __NZB_Grab(self, trigger):
		network = trigger.wrap.name.lower()
		chan = trigger.target.lower()
		url = trigger.match.group(1)
		
		# Make sure they're in an allowed channel
		if network not in self.Options['commands'] or chan not in self.Options['commands'][network]:
			tolog = "%s on %s/%s trying to grab a torrent." % (trigger.userinfo, network, chan)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Make sure they have the right user mode
		if self.Options.get('need_mode', None):
			hasmode = 0
			for mode in self.Options['need_mode']:
				if trigger.wrap.ircul.user_has_mode(chan, trigger.userinfo.nick, mode):
					hasmode = 1
					break
			
			if hasmode == 0:
				self.sendReply(trigger, "Access denied.")
				tolog = "%s on %s/%s trying to grab a torrent." % (trigger.userinfo, network, chan)
				self.putlog(LOG_WARNING, tolog)
				return
		
		# If the user has the grabany flag, go for it
		if self.Userlist.Has_Flag(trigger.userinfo, 'GrabNZB', 'grabany'):
			found = 1
		
		# See if the URL matches any of our regexps
		else:
			found = 0
			uq_url = UnquoteURL(url)
			
			for r in self.__grab_res:
				if r.match(uq_url):
					found = 1
					break
		
		# If we found something, grab it
		if found:
			self.sendReply(trigger, "Downloading NZB...")
			
			tolog = "%s on %s/%s asked me to download an NZB" % (trigger.userinfo, network, chan)
			self.putlog(LOG_ALWAYS, tolog)
			
			# See if it's a newzbin url
			m = NEWZBIN_URL_RE.match(url)
			if m:
				data = {
					'username': self.Options['newzbin_user'],
					'password': self.Options['newzbin_pass'],
					'reportid': m.group(1),
				}
				trigger._reportid = m.group(1)
				self.urlRequest(trigger, self.__Save_Newzbin, DNZB_URL, data)
			
			# Maybe newzleech
			else:
				m = NEWZLEECH_URL_RE.match(url)
				if m:
					self.urlRequest(trigger, self.__Parse_Newzleech, url)
				
				# Oh well
				else:
					self.urlRequest(trigger, self.__Save_NZB, url)
		
		# And if we didn't, cry
		else:
			self.sendReply(trigger, "That URL is not allowed.")
			
			tolog = "%s on %s/%s tried to grab torrent: %s" % (trigger.userinfo, network, chan, url)
			self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Save a Newzbin NZB
	def __Save_Newzbin(self, trigger, resp):
		if resp.response == '200':
			# Get the filename
			newname = resp.headers.get('x-dnzb-name', None)
			if newname is None:
				newname = 'msgid_%s' % (trigger._reportid)
			newname = SafeFilename(newname + '.nzb')
			newpath = os.path.join(self.Options['nzb_dir'], newname)
			
			# Save data
			open(newpath, 'wb').write(resp.data)
			
			# Send reply
			replytext = 'NZB saved as %s' % (newname)
			self.sendReply(trigger, replytext)
		
		# Error
		else:
			rcode = int(resp.headers['x-dnzb-rcode'])
			
			# Bad request
			if rcode == 400:
				err = 'bad request.'
			# Auth failed
			elif rcode == 401:
				err = 'authentication failed.'
			# Payment required
			elif rcode == 402:
				err = 'payment required/not premium account.'
			# Not found
			elif rcode == 404:
				err = 'report does not exist.'
			# Try again later
			elif rcode == 450:
				text = resp.headers.get('x-dnzb-rtext', '')
				m = re.search('wait (\d+) seconds', text)
				if m:
					wait = int(m.group(1)) + 1
					err = 'rate limited, please wait %ds.' % (wait)
				else:
					err = 'failed to parse wait response: %r' % (text)
					return
			# Internal server error
			elif rcode == 500:
				err = 'internal server error.'
			# Service unavailable
			elif rcode == 503:
				err = 'service unavailable.'
			# Unknown
			else:
				err = 'unknown error code: %s' % (rcode)
			
			replytext = 'Newzbin error: %s' % (err)
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse a Newzleech post page
	def __Parse_Newzleech(self, trigger, resp):
		if resp.response == '200':
			data = [ ('getnzb', 'Get NZB'), ]
			
			form = FindChunk(resp.data, '<form name="top"', '</form>') or FindChunk(resp.data, '<form action="" method="POST"', '</form>')
			if not form:
				self.sendReply(trigger, 'Error parsing page: form.')
				return
			
			inputs = FindChunks(form, '<input ', '>')
			if not inputs:
				self.sendReply(trigger, 'Error parsing page: inputs.')
				return
			
			# Build our POST data
			for i in inputs:
				iname = FindChunk(i, 'name="', '"')
				itype = FindChunk(i, 'type="', '"')
				ivalue = FindChunk(i, 'value="', '"')
				
				if not iname or not itype or not ivalue:
					continue
				
				if itype in ('hidden', 'checkbox'):
					data.append((iname, ivalue))
			
			# And fetch it
			if '/posts/' in resp.url:
				self.urlRequest(trigger, self.__Save_NZB, resp.url, data)
			else:
				self.urlRequest(trigger, self.__Save_NZB, NEWZLEECH_GET_URL, data)
	
	# -----------------------------------------------------------------------
	# Save a normal NZB
	def __Save_NZB(self, trigger, resp):
		if resp.response == '200':
			# Very basic check that it's an NZB
			if '<nzb' not in resp.data[:1000].lower():
				replytext = "Error: that doesn't seem to be an NZB file!"
				self.sendReply(trigger, replytext)
				return
			
			# Try to get a useful filename
			newname = resp.headers.get('content-disposition', None)
			if newname:
				m = CD_FILENAME_RE.search(newname)
				if m:
					newname = m.group(1)
					if newname.startswith('"') and newname.endswith('"'):
						newname = newname[1:-1]
				else:
					newname = None
			
			if newname is None:
				parts = urlparse.urlparse(resp.url)
				newname = parts[2].split('/')[-1]
			
			if not newname.endswith('.nzb'):
				newname = '%s.nzb' % (newname)
			
			newname = SafeFilename(newname)
			
			newpath = os.path.join(self.Options['nzb_dir'], newname)
			
			# Save data
			open(newpath, 'wb').write(resp.data)
			
			# Send reply
			replytext = 'NZB saved as %s' % (newname)
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
