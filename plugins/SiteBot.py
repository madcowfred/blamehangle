# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
A glFTPd sitebot plugin. Doesn't make much sense to maintain a pile of code
for a seperate bot when there's already a nice framework here :)

Different style to the other plugins, as we use a single command trigger with
our own command matching.
"""

import os
import re

# ---------------------------------------------------------------------------

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

SITEBOT_COMMAND = 'SITEBOT_COMMAND'

USER_RE = re.compile(r'^\w+$')

# ---------------------------------------------------------------------------

class SiteBot(Plugin):
	def setup(self):
		self.__partial = None
		
		self.rehash()
	
	def rehash(self):
		# Basic config stuff
		self.__channels = self.Config.get('sitebot', 'channels').lower().split()
		self.__command_prefix = self.Config.get('sitebot', 'command_prefix')
		self.__glftpd_path = self.Config.get('sitebot', 'glftpd_path')
		self.__site_name = self.Config.get('sitebot', 'site_name')
		
		# Get our list of paths for df
		self.__df_paths = []
		for option in self.Config.options('sitebot-df'):
			self.__df_paths.append(self.Config.get('sitebot-df', option).split(None, 1))
		
		self.__df_paths.sort()
		
		# Set up our horrible targets
		self.__logme = {}
		
		sections = [s for s in self.Config.sections() if s.startswith('sitebot.')]
		for section in sections:
			network = section.split('.', 1)[1]
			
			for option in self.Config.options(section):
				bits = self.Config.get(section, option).split()
				chan = bits[0]
				for logtype in bits[1:]:
					self.__logme.setdefault(logtype.upper(), {}).setdefault(network, []).append(chan)
		
		# Open the log and seek to the end
		logfile = os.path.join(self.__glftpd_path, 'ftp-data/logs/glftpd.log')
		self.__logfile = open(logfile, 'r')
		self.__logfile.seek(0, 2)
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		regexp = '^%s(.+)$' % self.__command_prefix
		self.setTextEvent(SITEBOT_COMMAND, re.compile(regexp), IRCT_PUBLIC)
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# See if our log file has any new lines
	def run_sometimes(self, currtime):
		lines = self.__logfile.readlines()
		# No lines, we reset EOF
		if not lines:
			self.__logfile.seek(0, 1)
			return
		
		for line in lines:
			if self.__partial:
				line = self.__partial + line
				self.__partial = None
			
			if not line.endswith('\n'):
				self.__partial = line
				break
			
			# Split the line up into date and text
			parts = line.strip().split(None, 5)
			
			if len(parts) != 6:
				tolog = 'BAD LINE: %s' % line
				self.putlog(LOG_DEBUG, tolog)
			
			# See if we handle it
			logtype, data = parts[5].split(':', 1)
			
			if logtype.find(' ') >= 0:
				logtype = logtype.split()[0]
			
			name = 'parse_%s' % logtype.lower()
			if hasattr(self, name):
				replytext = getattr(self, name)(data[1:])
				self.putlog(LOG_DEBUG, replytext)
				
				# Spruce it up a bit
				replytext = '\02(\02%s\02)\02 %s' % (self.__site_name, replytext)
				
				# Spit it out somewhere? Yikes.
				targets = self.__Get_Targets(logtype)
				if targets:
					self.privmsg(targets, None, replytext)
	
	# -----------------------------------------------------------------------
	# Horrible target logic goes here
	def __Get_Targets(self, logtype):
		targets = {}
		
		logtype = logtype.upper()
		
		# Some channels want this specific log type
		if logtype in self.__logme:
			targets = self.__logme[logtype]
		
		# Some channels want everything we understand
		if 'ALL' in self.__logme:
			if targets:
				more = self.__logme['ALL']
				# Combine them!
				for network, chans in more.items():
					if network not in targets:
						targets[network] = chans
					else:
						for chan in chans:
							if chan not in targets[network]:
								targets[network].append(chan)
			
			else:
				targets = self.__logme['ALL']
		
		return targets
	
	# -----------------------------------------------------------------------
	
	def parse_newdir(self, data):
		# "dir" "user" "group" "tagline"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(.*?)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return 'NEW: %s@%s drops %s in %s' % (m.group(2), m.group(3), rel, base)
	
	def parse_deldir(self, data):
		# "dir" "user" "group" "tagline"
		m = re.match(r'^"(.*?)" "(\S+)" "(\S+)" ".*?"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return 'DELDIR: %s@%s threw %s in the trash' % (m.group(2), m.group(3), rel)
	
	def parse_wipe(self, data):
		# "dir" "user" "group" "tagline"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(.*?)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return 'WIPED: %s@%s wiped the floor with %s' % (m.group(2), m.group(3), rel)
	
	# ----------------------------------------------------------------------------
	
	def parse_sfv(self, data):
		# "dir" "user" "group" "sfv_base_name?" "files"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return '\x02SFV\x02: %s/%s - [Files: \x02%s\x02 expected]' % (base, rel, m.group(5))
	
	def parse_firstfile(self, data):
		# "dir" "user" "group" "file" "speed"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return '\x02FIRST\x02: %s@%s uploads the first file of %s/%s at \x02%s\x02KB/s' % (m.group(2), m.group(3), base, rel, m.group(5))
	
	def parse_newracer(self, data):
		# "dir" "user" "group" "file" "speed" "remain" "others"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(.*?)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return '\x02RACER\x02: %s@%s joins the %s/%s race against [ %s ] at \x02%s\x02KB/s - [Files remaining: \x02%s\x02]' % (m.group(2), m.group(3), base, rel, m.group(7), m.group(5), m.group(6))
	
	def parse_update(self, data):
		# "dir" "percent" "user" "group" "u_files" "u_kbytes" "t_files" "t_kbytes" "remain" "eta"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return '\x02UPDATE\x02: %s/%s - At \x02%s\x02%%, %s@%s is leading with %s/%s files (%s/%sKB) - ETA: %s' % (base, rel, m.group(2), m.group(3), m.group(4), m.group(5), m.group(7), m.group(6), m.group(8), m.group(10))
	
	def parse_complete(self, data):
		# "dir" "t_files" "t_kbytes" "t_users" "t_groups" "avgspeed" "time" "f_user" "f_speed" "s_user" "s_speed"
		m = re.match(r'^"(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)" "(\S+)"$', data)
		if m:
			base, rel = Split_Dir(m.group(1))
			return '\x02COMPLETED\x02: %s/%s [\x02%s\x02 file(s) totalling \x02%s\x02KB] - [Upload took \x02%s\x02, average speed \x02%s\x02KB/s]' % (base, rel, m.group(2), m.group(3), m.group(7), m.group(6))
	
	# ----------------------------------------------------------------------------
	
	def _trigger_SITEBOT_COMMAND(self, trigger):
		# Don't talk to people not in our channels
		if trigger.target.lower() not in self.__channels:
			return
		
		# See if we know what they're on about
		bits = trigger.match.group(1).split()
		
		findme = '_cmd_%s' % bits[0].lower()
		if hasattr(self, findme):
			replytext = '\02(\02%s\02)\02 %s' % (self.__site_name, getattr(self, findme)(bits[1:]))
			self.sendReply(trigger, replytext, process=0)
	
	# -----------------------------------------------------------------------
	# Current bandwidth
	def _cmd_bw(self, params):
		# Make sure we can see the command
		ftpwho = os.path.join(self.__glftpd_path, 'bin/ftpwho')
		if not os.access(ftpwho, os.X_OK):
			return
		
		# Read the data from it
		p_in, p_out = os.popen2(ftpwho)
		p_in.close()
		
		lines = [l.strip() for l in p_out.readlines()]
		p_out.close()
		
		# No-one home
		if lines[0] == 'No Users Currently On Site!':
			replytext = 'There is no-one logged in!'
		
		# Someone home. Tally it up!
		else:
			down_speed = 0.0
			down_users = 0
			idle_users = 0
			up_speed = 0.0
			up_users = 0
			
			for line in lines[3:-1]:
				parts = [f.strip() for f in line.split('|') if f.strip()]
				if len(parts) != 4:
					continue
				
				# Idler
				if parts[3].startswith('Idle:'):
					idle_users += 1
				
				# Downloader
				elif parts[3].startswith('Dn:'):
					try:
						speed = parts[3].split()[-1][:-5]
						down_speed += float(speed)
						down_users += 1
					except:
						continue
				
				# Uploader
				elif parts[3].startswith('Up:'):
					try:
						speed = parts[3].split()[-1][:-5]
						up_speed += float(speed)
						up_users += 1
					except:
						continue
			
			# Do the stat dance
			parts = []
			
			def users(n):
				if n == 1:
					return '1 user'
				else:
					return '%d users' % n
			
			# Downloaders
			if down_users:
				part = '\02[\02Down: %s @ %sKB/s\02]\02' % (users(down_users), down_speed)
			else:
				part = '\02[\02Down: %s\02]\02' % (users(down_users))
			parts.append(part)
			
			# Uploaders
			if up_users:
				part = '\02[\02Up: %s @ %sKB/s\02]\02' % (users(up_users), up_speed)
			else:
				part = '\02[\02Up: %s\02]\02' % (users(up_users))
			parts.append(part)
			
			# Idlers
			part = '\02[\02Idle: %s\02]\02' % (users(idle_users))
			parts.append(part)
			
			replytext = ' '.join(parts)
		
		# Spit it out
		replytext = 'BANDWIDTH: %s' % replytext
		return replytext
	
	_cmd_usage = _cmd_bw
	
	# -----------------------------------------------------------------------
	# Disk usage
	def _cmd_df(self, params):
		chunks = []
		
		for path, display in self.__df_paths:
			if path.startswith('/'):
				path = path[1:]
			disk = os.path.join(self.__glftpd_path, path)
			
			if hasattr(os, 'statvfs'):
				try:
					info = os.statvfs(disk)
				except OSError:
					chunk = '[\x1f%s\x1f: ERROR]' % display
				else:
					# block size * total blocks
					totalmb = info[1] * info[2] / 1024 / 1024
					# block size * free blocks for non-superman
					freemb = info[1] * info[4] / 1024 / 1024
					
					chunk = '[\x1f%s\x1f: %dMB]' % (display, freemb)
				
				chunks.append(chunk)
			
			else:
				cmdline = '/bin/df -k %s' % disk
				lines = os.popen(cmdline, 'r').readlines()
				parts = lines[1].split()
				
				if len(parts) >= 4:
					totalmb = long(parts[1]) / 1024
					freemb = long(parts[3]) / 1024
					
					chunk = '[\x1f%s\x1f: %dMB]' % (display, freemb)
				else:
					chunk = '[\x1f%s\x1f: ERROR]' % display
				
				chunks.append(chunk)
		
		# Build the reply string
		replytext = 'DISK SPACE: %s' % ' '.join(chunks)
		return replytext
	
	# -----------------------------------------------------------------------
	# Info on a user
	def _cmd_info(self, params):
		# Idiots.
		if len(params) != 1:
			return 'Usage: info <user>'
		
		username = params[0]
		
		# Bad user, piss off
		if not USER_RE.match(username):
			return 'ERROR: illegal username!'
		
		# See if they have a file
		userpath = 'ftp-data/users/%s' % (username)
		userfile = os.path.join(self.__glftpd_path, userpath)
		
		if not os.access(userfile, os.R_OK):
			return 'ERROR: user does not exist!'
		
		# Read it, woo
		fields = {}
		f = open(userfile, 'r')
		
		for line in f:
			line = line.strip()
			parts = line.split(None, 1)
			if len(parts) != 2:
				continue
			
			if parts[0] == 'FLAGS':
				fields['flags'] = parts[1]
			elif parts[0] == 'TAGLINE':
				fields['tagline'] = parts[1]
			elif parts[0] == 'ALLUP':
				values = parts[1].split()
				fields['allup'] = int(values[1]) / 1024.0
			elif parts[0] == 'ALLDN':
				values = parts[1].split()
				fields['alldn'] = int(values[1]) / 1024.0
			elif parts[0] == 'GROUP':
				fields['group'] = parts[1]
		
		f.close()
		
		# Build the reply string
		s = 'INFO: %s@%s \02[\02Flags: %s\02]\02 \02[\02Tagline: %s\02]\02'
		s += ' \02[\02Up: %.1fMB\02]\02 \02[\02Down: %.1fMB\02]\02'
		replytext = s % (username, fields['group'], fields['flags'], fields['tagline'],
			fields['allup'], fields['alldn'])
		return replytext

# ---------------------------------------------------------------------------

def Split_Dir(dirname):
	# If it's a CDn or Sample directory, tack the parent onto the
	# release name
	dir_parts = dirname.split('/')
	
	n = re.match(r'^(CD\d+|Sample)$', dir_parts[-1], re.I)
	if n:
		base = dir_parts[-3]
		rel = '%s/%s' % (dir_parts[-2], dir_parts[-1])
	else:
		base = dir_parts[-2]
		rel = dir_parts[-1]
	
	return (base, rel)

# --------------------------------------------------------------------------------
