import socket
import time
import types

from classes.Constants import *
from classes.Userlist import Userlist

from classes.irclib import ServerConnectionError, STATUS_DISCONNECTED, STATUS_CONNECTING, STATUS_CONNECTED

# ---------------------------------------------------------------------------

CONNECT_TIMEOUT = 40
CONNECT_HOLDOFF = 5

OUTPUT_INTERVAL = 1

STONED_INTERVAL = 40
STONED_COUNT = 3

MAX_LINE_LENGTH = 400
MAX_SPLIT_LINES = 3

# ---------------------------------------------------------------------------

class WrapConn:
	"""
	Wraps an irclib.ServerConnection object and the various data we keep about
	it.
	"""
	
	def __init__(self, parent, network, conn, options):
		self.parent = parent
		self.network = network
		self.conn = conn
		self.options = options
		
		self.connect_id = 0
		
		# has ChatterGizmo asked us to close this connection?
		# (note, this flag is only inspected in ChatterGizmo, it is never
		#  touched here)
		self.requested_quit = 0
		
		# Reset ourselves to the disconnected state
		self.disconnected()
		
		# Parse the server list
		self.servers = []
		for server in options['servers'].split():
			parts = server.split(':')
			if len(parts) == 1:
				self.servers.append( (parts[0], 6667) )
			elif len(parts) == 2:
				self.servers.append( (parts[0], int(parts[1])) )
			else:
				print 'invalid server thing'
		
		self.channels = self.options['channels'].split()
		self.nicks = self.options['nicks'].split()
		
		self.realname = self.options.get('realname', 'blamehangle!')
		self.vhost = self.options.get('vhost', None)
		if self.vhost and not hasattr(socket, 'gaierror'):
			self.parent.connlog("vhost is set, but socket module doesn't have getaddrinfo()!")
			self.vhost = None
		
		self.ignore_strangers = int(self.options.get('ignore_strangers', 0))
	
	def connlog(self, level, text):
		self.parent.connlog(self.conn, level, text)
	
	def connect(self):
		nick = self.nicks[self.trynick]
		password = None
		
		self.server = self.servers[0]
		host, port = self.server
		
		
		tolog = 'Connecting to %s:%d...' % (host, port)
		self.connlog(LOG_ALWAYS, tolog)
		
		
		try:
			self.conn.connect(	host, port, nick,
								username=self.options['username'],
								ircname=self.realname,
								vhost=self.vhost
								)
		
		except ServerConnectionError, x:
			if type(x) in (types.ListType, types.TupleType):
				x = x[1]
			
			tolog = 'Connection failed: %s' % x
			self.connlog(LOG_ALWAYS, tolog)
			
			self.conn.status = STATUS_DISCONNECTED
		
		#else:
		#	self.status = STATUS_CONNECTING
		
		self.last_connect = time.time()
	
	def jump_server(self):
		if len(self.servers) > 1:
			server = self.servers.pop(0)
			self.servers.append(server)
		
		# Try and connect
		self.connect()
	
	# -----------------------------------------------------------------------
	# Reset ourselves to the disconnected state
	def disconnected(self):
		#self.status = STATUS_DISCONNECTED
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
	
	# Our nick is in use
	def nicknameinuse(self, nick):
		# While trying to connect!
		if self.conn.status == STATUS_CONNECTING:
			if nick == self.conn.real_nickname:
				if len(self.nicks) > 1:
					self.trynick += 1
					if self.trynick >= len(self.nicks):
						self.trynick = 0
					
					nick = self.nicks[self.trynick]
				
				else:
					nick = self.nicks[0]
					if len(nick) < 9:
						nick += '-'
					else:
						nick[-1] = '-'
				
				self.conn.nick(nick)
		
		# Nick is still in use, try again later
		elif self.conn.status == STATUS_CONNECTED:
			if nick != self.conn.real_nickname:
				self.last_nick = time.time()
	
	# -----------------------------------------------------------------------
	# Join the channels in our channel list
	def join_channels(self):
		for chan in self.channels:
			self.conn.join(chan)
	
	# Stuff outgoing data into our queues
	def privmsg(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:MAX_SPLIT_LINES]:
			self.__privmsg.append([target, line])
	
	def notice(self, target, text):
		lines = self.__Split_Text(text)
		for line in lines[:MAX_SPLIT_LINES]:
			self.__notice.append([target, text])
	
	def ctcp_reply(self, target, text):
		self.__ctcp_reply.append([target, text])
	
	# Split text into lines if it's too long
	def __Split_Text(self, text):
		# If it's not too long, give it back
		if len(text) <= MAX_LINE_LENGTH:
			return [text]
		
		# If it IS too long, split it
		else:
			found = 0
			
			for i in range(10, 100, 10):
				print i
				n = text.find(' ', MAX_LINE_LENGTH - i)
				if n >= 0 and n < MAX_LINE_LENGTH:
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
			if self.conn.real_nickname != self.nicks[0]:
				if currtime - self.last_nick >= 30:
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
			
			# Stoned check
			if (currtime - self.last_stoned) >= STONED_INTERVAL:
				self.last_stoned = currtime
				
				if self.stoned > STONED_COUNT:
					self.connlog(LOG_ALWAYS, "Server is stoned, disconnecting")
					self.conn.disconnect()
				else:
					self.stoned += 1
					self.privmsg(self.conn.real_nickname, "Stoned yet?")
