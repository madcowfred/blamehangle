# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Fairly simple plugin, downloads BitTorrent files and sticks them in a dir.
Can also announce when new files show up in a seperate directory, and give
a current torrent status report (requires my modified btlaunchmanycurses).
"""

import os
import re
import urlparse

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

GRABBT_CHECKDIR = 'GRABBT_CHECKDIR'

GRABBT_GRAB = 'GRABBT_GRAB'
GRAB_RE = re.compile(r'^grab (http://\S+)$')

GRABBT_TORRENTS = 'GRABBT_TORRENTS'
TORRENTS_RE = re.compile(r'^torrents$')

GRABBT_TORRENTSPACE = 'GRABBT_TORRENTSPACE'
TORRENTSPACE_RE = re.compile(r'^torrentspace$')

GRABBT_TORRENTSPEED = 'GRABBT_TORRENTSPEED'
TORRENTSPEED_RE = re.compile(r'^torrentspeed$')

# ---------------------------------------------------------------------------

class GrabBT(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self._torrent_dir = self.Config.get('grabbt', 'torrent_dir')
		self._new_dir = self.Config.get('grabbt', 'new_dir')
		self._status_file = self.Config.get('grabbt', 'status_file')
		self._http_base = self.Config.get('grabbt', 'http_base')
		
		# If the new dir is valid, get a list of it's files
		if self._new_dir and os.path.isdir(self._new_dir):
			self.__files = os.listdir(self._new_dir)
		else:
			self.__files = None
		
		# Work out our allowed channels
		self.__commands = {}
		for option in [o for o in self.Config.options('grabbt') if o.startswith('commands.')]:
			self.__commands[option[9:]] = self.Config.get('grabbt', option).split()
		
		self.__newfiles = {}
		for option in [o for o in self.Config.options('grabbt') if o.startswith('newfiles.')]:
			self.__newfiles[option[9:]] = self.Config.get('grabbt', option).split()
		
		if not self.__commands and not self.__newfiles:
			self.putlog(LOG_WARNING, "No channels configured!")
		
		# Compile our regexps
		self.__grab_res = []
		for option in self.Config.options('grabbt-re'):
			regexp = self.Config.get('grabbt-re', option)
			try:
				r = re.compile(regexp)
			except Exception, msg:
				tolog = "Failed to compile regexp '%s': %s" % (regexp, msg)
				self.putlog(LOG_WARNING, tolog)
			else:
				self.__grab_res.append(r)
	
	def register(self):
		# If we have to, start the check timer
		if self.__files is not None and self.__newfiles:
			self.setTimedEvent(GRABBT_CHECKDIR, 10, None)
			self.setTextEvent(GRABBT_TORRENTSPACE, TORRENTSPACE_RE, IRCT_PUBLIC_D)
		
		self.setTextEvent(GRABBT_GRAB, GRAB_RE, IRCT_PUBLIC_D)
		self.setTextEvent(GRABBT_TORRENTS, TORRENTS_RE, IRCT_PUBLIC_D)
		self.setTextEvent(GRABBT_TORRENTSPEED, TORRENTSPEED_RE, IRCT_PUBLIC_D)
		
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# It's time to see if we have any new files
	def _trigger_GRABBT_CHECKDIR(self, trigger):
		files = os.listdir(self._new_dir)
		for file in files:
			# If it's a new file, spam it
			if file not in self.__files:
				localfile = os.path.join(self._new_dir, file)
				filesize = os.path.getsize(localfile) / 1024 / 1024
				
				if self._http_base:
					replytext = '\x0303New file\x03: %s (%.1fMB) - %s%s' % (file, filesize, self._http_base, QuoteURL(file))
				else:
					replytext = '\x0303New file\x03: %s (%.1fMB)' % (file, filesize)
				
				self.privmsg(self.__newfiles, None, replytext)
		
		self.__files = files
	
	# -----------------------------------------------------------------------
	# Someone wants us to get a torrent
	def _trigger_GRABBT_GRAB(self, trigger):
		network = trigger.conn.options['name'].lower()
		url = trigger.match.group(1)
		
		# Make sure they're in an allowed channel
		if network not in self.__commands or trigger.target not in self.__commands[network]:
			tolog = "%s (%s@%s) on %s/%s trying to grab a torrent." % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# If the user has the grabany flag, go for it
		if self.Userlist.Has_Flag(trigger.userinfo, 'GrabBT', 'grabany'):
			found = 1
		
		# See if the URL matches any of our regexps
		else:
			found = 0
			
			for r in self.__grab_res:
				if r.match(url):
					found = 1
					break
		
		# If we found something, grab it
		if found:
			self.sendReply(trigger, "Downloading torrent...")
			self.urlRequest(trigger, self.__Save_Torrent, url)
			
			tolog = "%s (%s@%s) on %s/%s asked me to download a torrent" % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target)
			self.putlog(LOG_ALWAYS, tolog)
		
		# And if we didn't, cry
		else:
			self.sendReply(trigger, "That URL is not allowed.")
			
			tolog = "%s (%s@%s) on %s/%s tried to grab torrent: %s" % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target, url)
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
		
		# Split the last bit of the URL off
		torrentfile = UnquoteURL(resp.url.split('/')[-1])
		
		# Bad news, look for a Content-Disposition header
		if not torrentfile.endswith('.torrent'):
			for header in resp.headers:
				if header.lower().startswith('content-disposition'):
					chunks = header.split(None, 1)
					if len(chunks) < 2:
						break
					
					m = re.search('filename="(.*?)"', chunks[1])
					if m:
						torrentfile = m.group(1)
						break
		
		# Bad news, do evil parsing of the URL
		if not torrentfile.endswith('.torrent'):
			parsed = urlparse.urlparse(resp.url)
			if parsed[4]:
				parts = [s.split('=') for s in parsed[4].split('&')]
				for key, val in parts:
					if val.endswith('.torrent'):
						torrentfile = val
						break
		
		# Bad news, give up
		if not torrentfile.endswith('.torrent'):
			self.sendReply(trigger, "That doesn't seem to point to a torrent!")
			return
		
		torrentpath = os.path.join(self._torrent_dir, torrentfile)
		
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
	def _trigger_GRABBT_TORRENTS(self, trigger):
		network = trigger.conn.options['name'].lower()
		
		if network not in self.__commands or trigger.target not in self.__commands[network]:
			tolog = "%s (%s@%s) on %s/%s trying to list torrents." % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Get the list of torrents
		lines = open(self._status_file, 'r').readlines()
		
		if lines:
			for line in lines:
				filename, status, filesize, downtotal, downrate, uptotal, uprate = line.strip().split('|')
				
				downtotal = '%.1f' % (float(downtotal))
				downrate = '%.1f' % (float(downrate) / 1024)
				uptotal = '%.1f' % (float(uptotal))
				uprate = '%.1f' % (float(uprate) / 1024)
				
				line = '%s (%s MB) :: \x02[\x02%s\x02]\x02 \x02[\x02Down: %s MB (%s KB/s)\x02]\x02 \x02[\x02Up: %s MB (%s KB/s)\x02]\x02' % (filename, filesize, status, downtotal, downrate, uptotal, uprate)
				self.sendReply(trigger, line)
		
		else:
			self.sendReply(trigger, "No torrents active.")
	
	# -----------------------------------------------------------------------
	# Someone wants to see some total torrent speed.
	def _trigger_GRABBT_TORRENTSPEED(self, trigger):
		network = trigger.conn.options['name'].lower()
		
		if network not in self.__commands or trigger.target not in self.__commands[network]:
			tolog = "%s (%s@%s) on %s/%s trying to see torrent speed." % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# Get the list of torrents
		lines = open(self._status_file, 'r').readlines()
		
		if lines:
			down = up = 0.0
			
			for line in lines:
				filename, status, filesize, downtotal, downrate, uptotal, uprate = line.strip().split('|')
				
				down += (float(downrate) / 1024)
				up += (float(uprate) / 1024)
			
			line = 'Total torrent bandwidth: %.1fKB/s down, %.1fKB/s up' % (down, up)
			self.sendReply(trigger, line)
		
		else:
			self.sendReply(trigger, "No torrents active.")
	
	# -----------------------------------------------------------------------
	# Someone wants to see how much disk space we have free.
	def _trigger_GRABBT_TORRENTSPACE(self, trigger):
		network = trigger.conn.options['name'].lower()
		
		if network not in self.__commands or trigger.target not in self.__commands[network]:
			tolog = "%s (%s@%s) on %s/%s trying to see torrent speed." % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host, network, trigger.target)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# See how much disk space we have then
		if hasattr(os, 'statvfs'):
			try:
				info = os.statvfs(self._new_dir)
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
			cmdline = '/bin/df -k %s' % self._new_dir
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
