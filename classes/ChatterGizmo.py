
import errno
import select

from classes import irclib

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
	
	def _handle_welcome(self, conn, event):
		#tolog = 'Connected to %s' % self.server_list[0]
		#self.putlog(LOG_ALWAYS, tolog)
		
		#self.status = STATUS_CONNECTED
		#self.__Connect_Last = time.time()
		
		#self.stoned = 0
		
		# Initialise the channels dictionary
		#self.__Users = UserList()
		
		# Start the stoned timer thing
		#self.__Stoned_Check()
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		print 'Welcome to Floston Paradise!'
