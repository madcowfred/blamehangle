# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Implements an asyncore based IRC thing.
"""

import asyncore
import re
import socket

# ---------------------------------------------------------------------------
# Some IRC servers suck, and can't follow the RFCs. We get to deal with it.
_linesep_regexp = re.compile('\r?\n')

# ---------------------------------------------------------------------------

class asyncIRC(asyncore.dispatcher_with_send):
	def __init__(self):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.__read_buf = ''
	
	# -----------------------------------------------------------------------
	# We've managed to connect
	def handle_connect(self):
		# on connect stuff here
	
	# There is some data waiting to be read
	def handle_read(self):
		self.__read_buf += self.recv(4096)
		
		# Split the data into lines. The last line is either incomplete or
		# empty, so keep it as our buffer.
		lines = __linesep_regexp.split(self.__read_buf)
		self.__read_buf = lines[-1]
		
		for line in lines[:-1]:
			pass
	
	# The connection got closed somehow
	def handle_close(self):
		self.close()
	
	# An exception occured somewhere
	def handle_error(self):
		_type, _value = sys.exc_info()[:2]
		
		if _type == 'KeyboardInterrupt':
			raise
		else:
			self.failed(_value)
	
	# -----------------------------------------------------------------------
	# Connect to a server and port
	def connect(self, host, port=6667, family=socket.AF_INET):
		# Create our socket
		self.create_socket(family, socket.SOCK_STREAM)
		
		# Try to connect. This will blow up if it can't resolve the host.
		try:
			self.connect((host, port))
		except socket.gaierror, msg:
			self.failed(msg)
		#else:
		#	self.last_activity = time.time()
	
	# Your basic 'send a line of text to the server' method
	def sendline(self, line, *args):
		if args:
			line = line % args
		self.send(line + '\r\n')
