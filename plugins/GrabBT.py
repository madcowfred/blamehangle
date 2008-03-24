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
Downloads BitTorrent files and sticks them in a configured directory.
"""

import os
import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

from classes.bdecode import bdecode

# ---------------------------------------------------------------------------

class GrabBT(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('GrabBT', autosplit=True)
		
		if not self.Options['commands']:
			self.putlog(LOG_WARNING, "GrabBT has no channels configured!")
		
		# Compile our regexps
		self.__grab_res = []
		for regexp in self.OptionsList('GrabBT-Allowed'):
			try:
				r = re.compile(regexp)
			except Exception, msg:
				tolog = "Failed to compile regexp '%s': %s" % (regexp, msg)
				self.putlog(LOG_WARNING, tolog)
			else:
				self.__grab_res.append(r)
	
	def register(self):
		self.addTextEvent(
			method = self.__Torrent_Grab,
			regexp = r'^grab (http://.+)$',
			IRCTypes = (IRCT_PUBLIC_D,),
		)
		self.addTextEvent(
			method = self.__Torrent_List,
			regexp = r'^torrents$',
			IRCTypes = (IRCT_PUBLIC_D,),
		)
		self.addTextEvent(
			method = self.__Torrent_Speed,
			regexp = r'^torrentspeed$',
			IRCTypes = (IRCT_PUBLIC_D,),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants us to get a torrent
	def __Torrent_Grab(self, trigger):
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
		if self.Userlist.Has_Flag(trigger.userinfo, 'GrabBT', 'grabany'):
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
			self.sendReply(trigger, "Downloading torrent...")
			self.urlRequest(trigger, self.__Save_Torrent, url)
			
			tolog = "%s on %s/%s asked me to download a torrent" % (trigger.userinfo, network, chan)
			self.putlog(LOG_ALWAYS, tolog)
		
		# And if we didn't, cry
		else:
			self.sendReply(trigger, "That URL is not allowed.")
			
			tolog = "%s on %s/%s tried to grab torrent: %s" % (trigger.userinfo, network, chan, url)
			self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Torrent grabbed
	def __Save_Torrent(self, trigger, resp):
		# Error!
		if resp.response == '403':
			self.sendReply(trigger, 'Torrent needs a password!')
			return
		elif resp.response == '404':
			self.sendReply(trigger, 'Torrent does not exist!')
			return
		
		# Try parsing it
		try:
			metainfo = bdecode(resp.data)['info']
		except ValueError:
			self.sendReply(trigger, "That doesn't seem to point to a torrent!")
			return
		else:
			torrentfile = SafeFilename(metainfo['name'])
		
		torrentfile = '%s.torrent' % (torrentfile)
		torrentpath = os.path.join(self.Options['torrent_dir'], torrentfile)
		
		# Don't overwrite
		if os.path.exists(torrentpath):
			self.sendReply(trigger, 'That torrent already exists!')
			return
		
		# Save it
		try:
			open(torrentpath, 'wb').write(resp.data)
		except Exception, msg:
			replytext = 'Torrent save failed: %s' % msg
			self.sendReply(trigger, replytext)
		else:
			replytext = 'Torrent saved as %s' % torrentfile
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to see how our torrents are doing.
	def __Torrent_List(self, trigger):
		network = trigger.wrap.name.lower()
		chan = trigger.target.lower()
		
		if network not in self.Options['commands'] or chan not in self.Options['commands'][network]:
			tolog = "%s on %s/%s trying to list torrents." % (trigger.userinfo, network, chan)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Get the list of torrents
		try:
			files = os.listdir(self.Options['session_dir'])
		except:
			self.putlog(LOG_WARNING, "Torrent status directory does not exist or is unaccessible.")
			self.sendReply(trigger, "Status directory no worky!")
			return
		
		# Parse 'em
		lines = []
		for filename in files:
			if not filename.endswith('.torrent'):
				continue
			
			filepath = os.path.join(self.Options['session_dir'], filename)
			try:
				metainfo = bdecode(open(filepath, 'rb').read())
			except ValueError:
				tolog = '%r is not a valid torrent' % (filename)
				self.putlog(LOG_WARNING, tolog)
				continue
			except Exception, m:
				tolog = 'Error reading %r - %s' % (filename, m)
				self.putlog(LOG_WARNING, tolog)
				continue
			
			# Various stats
			if 'files' in metainfo['info']:
				total_size = sum(int(f['length']) for f in metainfo['info']['files'])
			else:
				total_size = metainfo['info']['length']
			
			torrent_name = os.path.basename(metainfo['rtorrent']['tied_to_file'])
			piece_length = metainfo['info']['piece length']
			down_total = metainfo['rtorrent']['chunks_done'] * piece_length
			up_total = metainfo['rtorrent']['total_uploaded']
			
			if down_total > 0:
				complete = (float(down_total) / float(total_size)) * 100
			else:
				complete = 0
			
			line = '%s (%s) :: %.1f%% complete - \x02[\x02Down: %s, Up: %s\x02]\x02' % (
				torrent_name, NiceSize(total_size), complete, NiceSize(down_total), NiceSize(up_total))
			lines.append(line)
		
		# Spit something out
		if lines:
			for line in lines:
				self.sendReply(trigger, line, process=0)
		else:
			self.sendReply(trigger, "No active torrents.")
	
	# -----------------------------------------------------------------------
	# Someone wants to see some total torrent speed.
	def __Torrent_Speed(self, trigger):
		network = trigger.wrap.name.lower()
		chan = trigger.target.lower()
		
		if network not in self.Options['commands'] or chan not in self.Options['commands'][network]:
			tolog = "%s on %s/%s trying to see torrent speed." % (trigger.userinfo, network, chan)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Get the list of torrents
		# Get the list of torrents
		try:
			lines = open(self.Options['status_file'], 'r').readlines()
		except:
			self.sendReply(trigger, "Couldn't open status file, no active torrents?")
			return
		
		if lines:
			down = up = 0.0
			
			for line in lines:
				try:
					filename, status, progress, filesize, seeds, peers, downtotal, downrate, uptotal, uprate = line.strip().split('|')
				except ValueError:
					continue
				
				down += float(downrate)
				up += float(uprate)
			
			down = down / 1024
			up = up / 1024
			
			line = 'Total torrent bandwidth: %.1fKB/s down, %.1fKB/s up' % (down, up)
			self.sendReply(trigger, line)
		
		else:
			self.sendReply(trigger, "No torrents active.")

# ---------------------------------------------------------------------------
