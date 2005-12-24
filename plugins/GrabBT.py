# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
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
Fairly simple plugin, downloads BitTorrent files and sticks them in a dir.
Can also announce when new files show up in a seperate directory, and give
a current torrent status report (requires my modified btlaunchmanycurses).
"""

import dircache
import os
import re
import urlparse

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
		
		# If the new dir is valid, get a list of it's files
		if self.Options['new_dir'] and os.path.isdir(self.Options['new_dir']):
			self.__files = dircache.listdir(self.Options['new_dir'])
		else:
			self.__files = None
		
		if not self.Options['commands'] and not self.Options['newfiles']:
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
		# If we have to, start the check timer and enable torrentspace
		if self.__files is not None and self.Options['newfiles']:
			self.addTimedEvent(
				method = self.__Torrent_Check,
				interval = 5,
			)
			self.addTextEvent(
				method = self.__Torrent_Space,
				regexp = r'^torrentspace$',
				IRCTypes = (IRCT_PUBLIC_D,),
			)
		
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
	# It's time to see if we have any new files
	def __Torrent_Check(self, trigger):
		files = dircache.listdir(self.Options['new_dir'])
		if files is self.__files:
			return
		
		# Spam the new files
		for file in [f for f in files if f not in self.__files]:
			localfile = os.path.join(self.Options['new_dir'], file)
			if not os.path.isfile(localfile):
				continue
			
			filesize = float(os.path.getsize(localfile)) / 1024 / 1024
			
			if self.Options['http_base']:
				replytext = '\x0303New file\x03: %s (%.1fMB) - %s%s' % (file, filesize, self.Options['http_base'], QuoteURL(file))
			else:
				replytext = '\x0303New file\x03: %s (%.1fMB)' % (file, filesize)
			
			self.privmsg(self.Options['newfiles'], None, replytext)
		
		self.__files = files
	
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
			lines = open(self.Options['status_file'], 'r').readlines()
		except:
			self.sendReply(trigger, "Couldn't open status file, no active torrents?")
			return
		
		if lines:
			for line in lines:
				try:
					filename, status, progress, filesize, seeds, peers, downtotal, downrate, uptotal, uprate = line.strip().split('|')
				except ValueError:
					continue
				
				downtotal = '%.1f' % (float(downtotal) / 1024 / 1024)
				downrate = '%.1f' % (float(downrate) / 1024)
				uptotal = '%.1f' % (float(uptotal) / 1024 / 1024)
				uprate = '%.1f' % (float(uprate) / 1024)
				
				line = '%s (%s) :: \x02[\x02%s (%s)\x02]\x02 \x02[\x02%s seeds, %s peers\x02]\x02 ' % (
					filename, NiceSize(filesize), status, progress, seeds, peers)
				line += '\x02[\x02Down: %s MB (%s KB/s)\x02]\x02 \x02[\x02Up: %s MB (%s KB/s)\x02]\x02' % (
					downtotal, downrate, uptotal, uprate)
				self.sendReply(trigger, line)
		
		else:
			self.sendReply(trigger, "No torrents active.")
	
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
	
	# -----------------------------------------------------------------------
	# Someone wants to see how much disk space we have free.
	def __Torrent_Space(self, trigger):
		network = trigger.wrap.name.lower()
		chan = trigger.target.lower()
		
		if network not in self.Options['commands'] or chan not in self.Options['commands'][network]:
			tolog = "%s on %s/%s trying to see torrent space." % (trigger.userinfo, network, chan)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# See how much disk space we have then
		if hasattr(os, 'statvfs'):
			try:
				info = os.statvfs(self.Options['new_dir'])
			except OSError:
				replytext = 'ERROR!'
			else:
				# block size * total blocks
				totalgb = float(info[1]) * info[2] / 1024 / 1024 / 1024
				# block size * free blocks for non-superman
				freegb = float(info[1]) * info[4] / 1024 / 1024 / 1024
				
				per = freegb / totalgb * 100
				replytext = '%.1fGB of %.1fGB (%d%%) free' % (freegb, totalgb, per)
		
		else:
			cmdline = '/bin/df -k %s' % self.Options['new_dir']
			lines = os.popen(cmdline, 'r').readlines()
			parts = lines[1].split()
			
			if len(parts) >= 4:
				totalgb = float(parts[1]) / 1024 / 1024
				freegb = float(parts[3]) / 1024 / 1024
				
				per = freegb / totalgb * 100
				replytext = '%.1fGB of %.1fGB (%d%%) free' % (freegb, totalgb, per)
			else:
				replytext = 'ERROR!'
		
		# Spit it out
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
