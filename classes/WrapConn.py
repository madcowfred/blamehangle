# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Wraps an asyncIRC connection and the various things we need to care about
into one object that's a lot easier to deal with.
"""

import random
import socket
import time
import types

from classes.asyncIRC import STATUS_DISCONNECTED, STATUS_CONNECTING, STATUS_CONNECTED
from classes.Constants import *
from classes.Userlist import Userlist

# ---------------------------------------------------------------------------
# How long in seconds to wait for a connect attempt to time out
CONNECT_TIMEOUT = 30
# How long in seconds to wait between connect attempts 
CONNECT_HOLDOFF = 5
# How long in seconds between sending lines to the server
OUTPUT_INTERVAL = 1
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

# ---------------------------------------------------------------------------

class WrapConn:
	"Wraps an asyncIRC object and the various data we keep about it."
	
	def __init__(self, parent, network, conn, options):
		self.parent = parent
		self.network = network
		self.conn = conn
		
		self.channels = {}
		
		self.dnswait = 0
		
		# We increment this to keep track of things like channel rejoin attempts
		self.connect_id = 0
		
		# has ChatterGizmo asked us to close this connection? (note: this flag
		# is only ever inspected in ChatterGizmo, it is never touched here)
		self.requested_quit = 0
		
		# Reset ourselves to the disconnected state
		self.disconnected()
		
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
				data = (parts[0], parts[1], None, [])
			elif len(parts) == 3:
				data = (parts[0], parts[1], parts[2], [])
			
			if data is not None:
				self.servers.append(data)
			else:
				tolog = "Invalid server definition: '%s'" % (server)
				self.connlog(LOG_WARNING, tolog)
		
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
			for chan in old_chans:
				if chan not in self.channels:
					self.conn.part(chan)
			
			self.join_channels()
		
		# Boring stuff
		self.nicks = options['nicks'].split()
		
		self.realname = options.get('realname', 'blamehangle!').strip() or 'blamehangle!'
		self.username = options.get('username', 'blamehangle').strip() or 'blamehangle'
		self.vhost = options.get('vhost', '').strip() or None
		if self.vhost and not hasattr(socket, 'gaierror'):
			self.connlog(LOG_WARNING, "vhost is set, but socket module doesn't have getaddrinfo()!")
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
	
	def connlog(self, level, text):
		newtext = '(%s) %s' % (self.name, text)
		self.parent.putlog(level, newtext)
	
	# -----------------------------------------------------------------------
	# Reset ourselves to the disconnected state
	def disconnected(self):
		self.stoned = 0
		self.trynick = 0
		
		self.last_connect = 0
		self.last_nick = 0
		self.last_output = 0
		self.last_stoned = 0
		
		# Outgoing queues
		self.__privmsg = []
		self.__notice = []
		self.__ctcp_reply = []
		
		self.users = Userlist()
	
	def connect(self):
		if self.dnswait:
			return
		
		if not self.servers:
			self.last_connect = time.time() + 25
			self.connlog(LOG_WARNING, "No servers defined for this connection!")
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
			self.connlog(LOG_ALWAYS, tolog)
		
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
				self.connlog(LOG_ALWAYS, tolog)
			
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
				self.connlog(LOG_ALWAYS, tolog)
				
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
	def join_channels(self):
		for chan in self.channels:
			self.join_channel(chan)
	
	def join_channel(self, chan):
		self.conn.join(chan, self.channels[chan])
	
	# -----------------------------------------------------------------------
	# Stuff outgoing data into our queues
	def privmsg(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:self.max_split_lines]:
			self.__privmsg.append([target, line])
	
	def notice(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:self.max_split_lines]:
			self.__notice.append([target, text])
	
	def ctcp_reply(self, target, text):
		self.__ctcp_reply.append([target, text])
	
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
				self.connlog(LOG_WARNING, 'Refusing to send extremely long un-splittable line!')
				return []
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		if self.conn.status == STATUS_DISCONNECTED and (currtime - self.last_connect) >= CONNECT_HOLDOFF:
			self.jump_server()
		
		# Connecting stuff
		elif self.conn.status == STATUS_CONNECTING and (currtime - self.last_connect) >= CONNECT_TIMEOUT:
			self.connlog(LOG_ALWAYS, "Connection failed: timed out")
			self.conn.disconnect()
		
		# Connected stuff!
		elif self.conn.status == STATUS_CONNECTED:
			# If we still don't have our nick, try again
			if self.conn.getnick() != self.nicks[0]:
				if currtime - self.last_nick >= 30:
					self.last_nick = currtime
					self.conn.nick(self.nicks[0])
			
			# Send some stuff from our output queues if we have to
			if (currtime - self.last_output) >= OUTPUT_INTERVAL:
				if self.__ctcp_reply or self.__notice or self.__privmsg:
					self.last_output = currtime
				
				if self.__ctcp_reply:
					target, text = self.__ctcp_reply.pop(0)
					self.conn.ctcp_reply(target, text)
				
				elif self.__notice:
					target, text = self.__notice.pop(0)
					self.conn.notice(target, text)
				
				elif self.__privmsg:
					target, text = self.__privmsg.pop(0)
					self.conn.privmsg(target, text)
			
			# Set our stoned time to now if we've just connected
			if self.last_stoned == 0:
				self.last_stoned = currtime
			
			# Stoned check
			elif (currtime - self.last_stoned) >= STONED_INTERVAL:
				self.last_stoned = currtime
				self.stoned += 1
				
				if self.stoned > STONED_COUNT:
					self.connlog(LOG_ALWAYS, "Server is stoned, disconnecting")
					self.conn.disconnect()
				else:
					self.privmsg(self.conn.getnick(), "Stoned yet?")

# ---------------------------------------------------------------------------
