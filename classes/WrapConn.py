STATUS_DISCONNECTED = 'Disconnected'
STATUS_CONNECTING = 'Connecting'
STATUS_CONNECTED = 'Connected'

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
	
	def __init__(self, conn, options):
		self.conn = conn
		self.options = options
		
		self.servers = []
		for server in options['servers'].split():
			parts = server.split(':')
			if len(parts) == 1:
				self.servers.append( (parts[0], 6667) )
			elif len(parts) == 2:
				self.servers.append( (parts[0], parts[1]) )
			else:
				print 'invalid server thing'
		
		self.channels = self.options['channels'].split()
	
	def join_channels(self):
		for chan in self.channels:
			self.conn.join(chan)
