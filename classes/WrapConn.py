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
	
	status = STATUS_DISCONNECTED
	stoned = 0
	
	last_connect = 0
	last_stoned = 0
	
	users = Userlist()
	
	def __init__(self, parent, conn, options):
		self.parent = parent
		self.conn = conn
		self.options = options
		
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
	
	def join_channels(self):
		for chan in self.channels:
			self.conn.join(chan)
