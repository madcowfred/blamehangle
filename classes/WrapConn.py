import time
import types

from classes.Constants import *
from classes.Userlist import Userlist

from classes.irclib import ServerConnectionError

# ---------------------------------------------------------------------------

STATUS_DISCONNECTED = 'Disconnected'
STATUS_CONNECTING = 'Connecting'
STATUS_CONNECTED = 'Connected'

# ---------------------------------------------------------------------------

class WrapConn:
	"""
	Wraps an irclib.ServerConnection object and the various data we keep about
	it.
	"""
	
	def __init__(self, parent, conn, options):
		self.parent = parent
		self.conn = conn
		self.options = options

		# nfi if this is what is needed...
		self.connect_id = 0
		
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
	
	def connect(self):
		nick = self.nicks[self.trynick]
		password = None
		
		self.server = self.servers[0]
		host, port = self.server
		
		
		tolog = 'Connecting to %s:%d...' % (host, port)
		self.parent.connlog(self.conn, LOG_ALWAYS, tolog)
		
		
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
			self.parent.connlog(self.conn, LOG_ALWAYS, tolog)
			
			self.status = STATUS_DISCONNECTED
		
		else:
			self.status = STATUS_CONNECTING
		
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
		self.status = STATUS_DISCONNECTED
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
		if self.status == STATUS_CONNECTING:
			if nick == self.conn.real_nickname:
				if len(self.nicks) > 1:
					self.trynick += 1
					if self.trynick >= len(self.nicks):
						self.trynick = 0
					
					nick = self.nicks[self.trynick]
				
				else:
					nick = self.nicknames[0]
					if len(nick) < 9:
						nick += '-'
					else:
						nick[8] = '-'
				
				self.conn.nick(nick)
		
		# Nick is still in use, try again later
		elif self.status == STATUS_CONNECTED:
			if nick != self.conn.real_nickname:
				self.last_nick = time.time()
	
	# -----------------------------------------------------------------------
	# Join the channels in our channel list
	def join_channels(self):
		for chan in self.channels:
			self.conn.join(chan)
	
	# Stuff outgoing data into our queues
	def privmsg(self, target, text):
		self.__privmsg.append([target, text])
	
	def notice(self, target, text):
		self.__notice.append([target, text])
	
	def ctcp_reply(self, target, text):
		self.__ctcp_reply.append([target, text])
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		# If we still don't have our nick, try again
		if self.conn.real_nickname != self.nicks[0]:
			if currtime - self.last_nick >= 30:
				self.conn.nick(self.nicks[0])
		
		# Send some stuff from our output queues if we have to
		if currtime - self.last_output >= 1:
			if self.__ctcp_reply:
				target, text = self.__ctcp_reply.pop(0)
				self.conn.ctcp_reply(target, text)
			
			elif self.__notice:
				target, text = self.__notice.pop(0)
				self.conn.notice(target, text)
			
			elif self.__privmsg:
				target, text = self.__privmsg.pop(0)
				self.conn.privmsg(target, text)
			
			else:
				return
			
			self.last_output = currtime
