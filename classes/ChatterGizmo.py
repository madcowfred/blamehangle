
import errno
import select

from classes import irclib
from classes.Userlist import Userlist

# ---------------------------------------------------------------------------
# Constants specific to this module
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
	
	def __init__(self, conn):
		self.conn = conn

# ---------------------------------------------------------------------------

class ChatterGizmo:
	"""
	The IRC class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def __init__(self, Config):
		self.__ircobj = irclib.IRC()
		
		self.Config = Config
		
		self.Conns = {}
	
	def main_loop(self):
		try:
			self.__ircobj.process_once()
		
		except select.error, msg:
			if msg[0] == errno.EINTR:
				pass
	
	# -----------------------------------------------------------------------
	
	def connect(self):
		
	
	# -----------------------------------------------------------------------
	
	def _handle_welcome(self, conn, event):
		#tolog = 'Connected to %s' % self.server_list[0]
		#self.putlog(LOG_ALWAYS, tolog)
		
		# Start the stoned timer thing
		#self.__Stoned_Check()
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		print 'Welcome to Floston Paradise!'
