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
Wraps an asyncIRC connection and the various things we need to care about
into one object that's a lot easier to deal with.
"""

import logging
import random
import socket
import time
import types

from classes.asyncIRC import STATUS_DISCONNECTED, STATUS_CONNECTING, STATUS_CONNECTED
from classes.Constants import *
from classes.IRCUserList import IRCUserList

# ---------------------------------------------------------------------------
# How long in seconds to wait for a connect attempt to time out
CONNECT_TIMEOUT = 30
# How long in seconds to wait between connect attempts 
CONNECT_HOLDOFF = 5
# How long in seconds between sending lines to the server
OUTPUT_INTERVAL = 1
# How long in seconds between trying to get our primary nickname back
NICKNAME_HOLDOFF = 15
# How long in seconds between channel join attempts
JOINS_INTERVAL = 15
# How long in seconds between 'stoned' checks
STONED_INTERVAL = 40
# How stoned must we be to jump server
STONED_COUNT = 3

# Range for line length to be
MIN_LINE_LENGTH = 200
MAX_LINE_LENGTH = 500
# Range for split lines to be
MIN_SPLIT_LINES = 1
MAX_SPLIT_LINES = 4

# Priority levels for output
PRIORITY_COMMAND = 0
PRIORITY_CTCPREPLY = 1
PRIORITY_NOTICE = 2
PRIORITY_PRIVMSG = 3

# ---------------------------------------------------------------------------

class WrapConn:
	"Wraps an asyncIRC object and the various data we keep about it."
	
	def __init__(self, parent, network, conn, options):
		self.logger = logging.getLogger('hangle.WrapConn')
		
		self.parent = parent
		self.network = network
		self.conn = conn
		
		self.channels = {}
		
		self.dnswait = 0
		self.wholist = []
		
		# We increment this to keep track of things like channel rejoin attempts
		self.connect_id = 0
		
		# has ChatterGizmo asked us to close this connection? (note: this flag
		# is only ever inspected in ChatterGizmo, it is never touched here)
		self.requested_quit = 0
		
		# Reset ourselves to the disconnected state
		self.reset()
		
		# Parse our options
		self.parse_options(options)
	
	def parse_options(self, options):
		self.name = options['name']
		
		# Parse the server list
		self.servers = []
		for server in options.get('server', {}).values():
			parts = server.split()
			data = None
			
			if len(parts) == 1:
				data = (parts[0], 6667, None, [])
			elif len(parts) == 2:
				data = (parts[0], int(parts[1]), None, [])
			elif len(parts) == 3:
				data = (parts[0], int(parts[1]), parts[2], [])
			
			if data is not None:
				self.servers.append(data)
			else:
				tolog = "Invalid server definition: '%s'" % (server)
				self.connlog(self.logger.warn, tolog)
		
		# Put the server list in a random order
		random.shuffle(self.servers)
		
		# Parse the channels
		old_chans = self.channels
		self.channels = {}
		
		for chunk in options.get('channel', {}).values():
			parts = chunk.split()
			if len(parts) == 1:
				self.channels[parts[0].lower()] = None
			else:
				self.channels[parts[0].lower()] = parts[1]
		
		# Update our channels if we're connected
		if self.conn.status == STATUS_CONNECTED:
			# Ditch the removed ones
			for chan in old_chans:
				if chan not in self.channels:
					self.conn.part(chan)
			
			# Join the new ones
			#for chan in self.channels:
			#	if chan not in old_chans:
			#		self.join_channel(chan)
		
		# Boring stuff
		self.nicks = options['nicks'].split()
		
		self.realname = options.get('realname', 'blamehangle!').strip() or 'blamehangle!'
		self.username = options.get('username', 'blamehangle').strip() or 'blamehangle'
		self.vhost = options.get('vhost', '').strip() or None
		if self.vhost and not hasattr(socket, 'gaierror'):
			self.connlog(self.logger.warn, "vhost is set, but socket module doesn't have getaddrinfo()!")
			self.vhost = None
		
		self.ignore_strangers = int(options.get('ignore_strangers', 0))
		self.combine_targets = int(options.get('combine_targets', 0))
		
		self.nickserv_nick = options.get('nickserv_nick', '').strip() or None
		self.nickserv_pass = options.get('nickserv_pass', '').strip() or None
		
		# Max line length should default to the max if there is no such option
		self.max_line_length = max(MIN_LINE_LENGTH, min(MAX_LINE_LENGTH, int(options.get('max_line_length', MAX_LINE_LENGTH))))
		# Max split lines should default to the min if there is no such option
		self.max_split_lines = max(MIN_SPLIT_LINES, min(MAX_SPLIT_LINES, int(options.get('max_split_lines', MIN_SPLIT_LINES))))
	
	# -----------------------------------------------------------------------
	
	def connlog(self, logfunc, tolog):
		newlog = '(%s) %s' % (self.name, tolog)
		logfunc(newlog)
	
	# -----------------------------------------------------------------------
	# Reset ourselves to the disconnected state
	def reset(self):
		self.stoned = 0
		self.trynick = 0
		
		self.last_connect = 0
		self.last_joins = 0
		self.last_nick = 0
		self.last_output = 0
		self.last_stoned = 0
		
		# Outgoing queue
		self.__outgoing = PriorityList()
		
		self.ircul = IRCUserList()
	
	def connect(self):
		if self.dnswait:
			return
		
		if not self.servers:
			self.last_connect = time.time() + 25
			self.connlog(self.logger.warn, "No servers defined for this connection!")
			return
		
		self.server = self.servers[0]
		
		self.dnswait = 1
		self.parent.dnsLookup(None, self.parent._DNS_Reply, self.server[0], self.conn.connid)
	
	# Jump to the next server in our list
	def jump_server(self):
		if len(self.servers) > 1:
			server = self.servers.pop(0)
			self.servers.append(server)
		
		self.connect()
	
	# -----------------------------------------------------------------------
	
	def really_connect(self, hosts):
		self.dnswait = 0
		self.last_connect = time.time()
		
		host = self.server[0]
		port = self.server[1]
		nick = self.nicks[self.trynick]
		password = self.server[2]
		
		# Resolve failure
		if hosts is None:
			tolog = 'Unable to resolve server: %s' % (host)
			self.connlog(self.logger.info, tolog)
		
		# Something useful happened
		else:
			if self.parent.use_ipv6:
				if self.parent.dns_order:
					new = []
					for f in self.parent.dns_order:
						new += [h for h in hosts if h[0] == int(f)]
					hosts = new
			else:
				hosts = [h for h in hosts if h[0] == 4]
			
			if hosts == []:
				tolog = "No usable IPs found for '%s'" % (host)
				self.connlog(self.logger.info, tolog)
			
			else:
				# We don't want to connect to an IP that we've tried recently
				ips = [h for h in hosts if h[1] not in self.server[3]]
				if not ips:
					del self.server[3][:]
					ips = hosts
				
				ip = ips[0][1]
				self.server[3].append(ip)
				
				# Off we go
				tolog = 'Connecting to %s (%s) port %d...' % (host, ip, port)
				self.connlog(self.logger.info, tolog)
				
				# IPv6 host, set the socket family
				if ips[0][0] == 6:
					family = socket.AF_INET6
				else:
					family = socket.AF_INET
				
				self.conn.connect_to_server(ip, port, nick,
											username=self.username,
											ircname=self.realname,
											vhost=self.vhost,
											family=family,
											)
	
	# -----------------------------------------------------------------------
	# Our nick is in use
	def nicknameinuse(self, nick):
		# While trying to connect!
		if self.conn.status == STATUS_CONNECTED and self.conn.welcomed == 0:
			gennick = 0
			
			# The nick we just tried is in use, ruh-roh
			if nick == self.nicks[self.trynick]:
				self.trynick = (self.trynick + 1) % len(self.nicks)
				if self.trynick == 0:
					gennick = 1
				else:
					newnick = self.nicks[self.trynick]
			# We probably tried a made up one, try again
			else:
				gennick = 1
			
			# Generate a silly new nick
			if gennick:
				# If it was already a generated nick, time to try a bit
				# of randomness.
				if nick not in self.nicks:
					newnick = nick[:(self.conn.features['nicklen'] - 2)]
					
					# 0-9 = 48-57, a-z = 97-122
					for i in range(2):
						n = random.randint(0, 1)
						if n == 0:
							newnick += chr(random.randint(48, 57))
						elif n == 1:
							newnick += chr(random.randint(97, 122))
				# Just try sticking a dash on the end
				else:
					newnick = self.nicks[0][:(self.conn.features['nicklen'] - 1)] + '-'
			
			# And off we go
			self.last_nick = time.time()
			self.conn.nick(newnick)
		
		# Nick is still in use, try again later
		elif self.conn.status == STATUS_CONNECTED:
			if nick != self.conn.getnick():
				self.last_nick = time.time()
	
	# -----------------------------------------------------------------------
	# Join the channels in our channel list
	def join_channels(self, *joinme):
		if not joinme:
			joinme = self.channels.keys()
		
		chans = []
		keys = []
		
		for chan in joinme:
			key = self.channels[chan]
			
			if key is None:
				chans.append(chan)
			else:
				chans.insert(0, chan)
				keys.insert(0, key)
		
		chanstring = ','.join(chans)
		if keys:
			keystring = ','.join(keys)
		else:
			keystring = None
		
		self.conn.join(chanstring, keystring)
	
	# -----------------------------------------------------------------------
	# Stuff outgoing data into our queue
	def sendline(self, text):
		self.__outgoing.priority_insert(PRIORITY_COMMAND, text)
	
	def ctcp_reply(self, target, text):
		self.__outgoing.priority_insert(PRIORITY_CTCPREPLY, target, text)
	
	def notice(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:self.max_split_lines]:
			self.__outgoing.priority_insert(PRIORITY_NOTICE, target, line)
	
	def privmsg(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:self.max_split_lines]:
			self.__outgoing.priority_insert(PRIORITY_PRIVMSG, target, line)
	
	# -----------------------------------------------------------------------
	# Split text into lines if it's too long
	def __Split_Text(self, text):
		# If it's not too long, give it back
		if len(text) <= self.max_line_length:
			return [text]
		
		# If it IS too long, split it
		else:
			found = 0
			
			for i in range(10, 100, 10):
				n = text.find(' ', self.max_line_length - i)
				if n >= 0 and n < self.max_line_length:
					found = 1
					break
			
			# Found somewhere to split, yay
			if found:
				lines = [text[:n]]
				leftover = text[n+1:]
				
				more_lines = self.__Split_Text(leftover)
				lines.extend(more_lines)
				
				return lines
			
			# Nowhere, argh!
			else:
				self.connlog(self.logger.warn, 'Refusing to send extremely long un-splittable line!')
				return []
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		if self.conn.status == STATUS_DISCONNECTED:
			if (currtime - self.last_connect) >= CONNECT_HOLDOFF:
				self.jump_server()
		
		# Connecting stuff
		elif self.conn.status == STATUS_CONNECTING:
			if (currtime - self.last_connect) >= CONNECT_TIMEOUT:
				self.connlog(self.logger.info, "Connection failed: timed out")
				self.conn.disconnect()
		
		# Connected stuff!
		elif self.conn.status == STATUS_CONNECTED:
			# If we still don't have our nick, try again
			if self.conn.getnick() != self.nicks[0]:
				if (currtime - self.last_nick) >= NICKNAME_HOLDOFF:
					self.last_nick = currtime
					self.conn.nick(self.nicks[0])
			
			# Send something from our output queue if we have to
			if (currtime - self.last_output) >= OUTPUT_INTERVAL:
				if self.__outgoing:
					self.last_output = currtime
					
					data = self.__outgoing.pop(0)
					
					if data[0] == PRIORITY_COMMAND:
						self.conn.sendline(data[1])
					elif data[0] == PRIORITY_CTCPREPLY:
						self.conn.ctcp_reply(data[1], data[2])
					elif data[0] == PRIORITY_NOTICE:
						self.conn.notice(data[1], data[2])
					elif data[0] == PRIORITY_PRIVMSG:
						self.conn.privmsg(data[1], data[2])
			
			if self.conn.welcomed == 1:
				# Set our join and stoned time to now if we've just connected
				if self.last_joins == 0 and self.last_stoned == 0:
					self.last_joins = self.last_stoned = currtime
					return
				
				# Joins check
				if (currtime - self.last_joins) >= JOINS_INTERVAL:
					self.last_joins = currtime
					
					# We want to join any channels that we're not currently on
					chans = self.ircul._c.keys()
					joinme = [c for c in self.channels.keys() if c not in chans]
					self.join_channels(*joinme)
				
				# Stoned check
				if (currtime - self.last_stoned) >= STONED_INTERVAL:
					self.last_stoned = currtime
					self.stoned += 1
					
					if self.stoned > STONED_COUNT:
						self.connlog(self.logger.info, "Server is stoned, disconnecting")
						self.conn.disconnect()
					else:
						self.privmsg(self.conn.getnick(), "Stoned yet?")
	
	# -----------------------------------------------------------------------
	# Are we connected?
	def connected(self):
		return (self.conn.status == STATUS_CONNECTED)

# ---------------------------------------------------------------------------
# Simple priority list, similar to the bisect module, but only sorting by the
# first value.
class PriorityList(list):
	def priority_insert(self, *data):
		if len(self) == 0:
			self.append(data)
		else:
			for i in range(len(self)):
				if self[i][0] > data[0]:
					self.insert(i, data)
					return
			self.append(data)

# ---------------------------------------------------------------------------
