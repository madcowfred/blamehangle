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

_linesep_regexp = re.compile('\r?\n')

# ---------------------------------------------------------------------------

class asyncIRC(asyncore.dispatcher_with_send):
	def __init__(self):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.__read_buf = ''
	
	def handle_connect(self):
		# on connect stuff here
	
	def handle_close(self):
		self.close()
	
	def handle_read(self):
		self.__read_buf += self.recv(4096)
		
		lines = __linesep_regexp.split(self.__read_buf)
		# Last line is either incomplete or empty, save it for later
		self.__read_buf = lines[-1]
		
		for line in lines[:-1]:
			pass
	
	def sendline(self, line, *args):
		if args:
			line = line % args
		self.send(line + '\r\n')
