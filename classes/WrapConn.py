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
	Wraps an irclib Connection object and the various data we keep about it
	into a moderately simple class.
	"""
	
	def __init__(self, parent, conn, options):
		self.parent = parent
		self.conn = conn
		self.options = options
		
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
		# Initialise the variables to default values
		self.trynick = self.nicks[0]
		password = None
		
		# Split up the server line into it's parts
		self.server = self.servers[0]
		
		host, port = self.server
		
		
		tolog = 'Connecting to %s:%d...' % (host, port)
		self.parent.connlog(self.conn, LOG_ALWAYS, tolog)
		
		
		try:
			self.conn.connect(	host, port, self.trynick,
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
	
	# Reset ourselves to the disconnected state
	def disconnected(self):
		self.status = STATUS_DISCONNECTED
		self.stoned = 0
		
		self.last_connect = 0
		self.last_output = 0
		self.last_stoned = 0
		
		# Outgoing queues
		self.__privmsg = []
		self.__notice = []
		self.__ctcp_reply = []
		
		self.users = Userlist()
	
	# Join the channels in our channel list
	def join_channels(self):
		for chan in self.channels:
			self.conn.join(chan)
	
	# -----------------------------------------------------------------------
	# Stuff outgoing data into our queues
	def privmsg(self, target, text):
		self.__privmsg.append([target, text])
	
	def notice(self, target, text):
		self.__notice.append([target, text])
	
	def ctcp_reply(self, target, text):
		self.__ctcp_reply.append([target, text])
	
	# Send some stuff to IRC whenever we feel like it
	def do_output(self, currtime):
		if self.status != STATUS_CONNECTED:
			return
		
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
			
			print 'sent stuff'
			
			self.last_output = currtime
