# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Implements an asyncore based IRC thing.

Some bits 'borrowed' from irclib.py by Joel Roshdal.
"""

import asyncore
import re
import socket

# ---------------------------------------------------------------------------
# Yes, this thing is horrible.
_command_regexp = re.compile(r'^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?')
# Some IRC servers suck, and can't follow the RFCs. We get to deal with it.
_linesep_regexp = re.compile(r'\r?\n')

# ---------------------------------------------------------------------------
# Shiny way to look at a user.
class UserInfo:
	def __init__(self, hostmask):
		self.hostmask = hostmask
		
		self.nick, rest = hostmask.split('!')
		self.ident, self.host = rest.split('@')

# Is this a channel?
def is_channel(s):
	return s and s[0] in "#&+!"

# ---------------------------------------------------------------------------

class asyncIRC(asyncore.dispatcher_with_send):
	def __init__(self):
		asyncore.dispatcher_with_send.__init__(self)
		
		# stuff we need to keep track of
		self.__handlers = []
		self.__nickname = None
		self.__read_buf = ''
	
	# -----------------------------------------------------------------------
	# Register something's interest in receiving events
	def register(self, method):
		self.__handlers.append(method)
	
	# An event happened, off we go
	def __trigger_event(self, command, prefix, target, arguments):
		for method in self.__handlers:
			method(command, prefix, target, arguments)
	
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
	
	# -----------------------------------------------------------------------
	# We've managed to connect
	def handle_connect(self):
		# on connect stuff here
	
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
	
	# There is some data waiting to be read
	def handle_read(self):
		self.__read_buf += self.recv(4096)
		
		# Split the data into lines. The last line is either incomplete or
		# empty, so keep it as our buffer.
		lines = __linesep_regexp.split(self.__read_buf)
		self.__read_buf = lines[-1]
		
		for line in lines[:-1]:
			prefix = command = arguments = userinfo = None
			m = _command_regexp.match(line)
			
			if m.group('prefix'):
				prefix = m.group('prefix')
				if prefix.find('!') >= 0:
					userinfo = UserInfo(prefix)
			
			if m.group('command'):
				command = m.group('command').lower()
			
			# not sure about this one
			if m.group('argument'):
				a = string.split(m.group("argument"), " :", 1)
				arguments = string.split(a[0])
				if len(a) == 2:
					arguments.append(a[1])
			
			# Keep our nickname up to date
			if command == '001':
				self.__nickname = arguments[0]
			elif command == 'nick' and userinfo.nick == self.__nickname:
				self.__nickname = arguments[0]
			
			# NOTICE/PRIVMSG are special
			if command in ('notice', 'privmsg'):
				target, message = arguments
				
				if command == 'privmsg':
					if is_channel(target):
						command = 'pubmsg'
				else:
					if is_channel(target):
						command = 'pubnotice'
					else:
						command = 'privnotice'
			
			else:
				if command not in ('quit', 'ping'):
					target = arguments[0]
					arguments = arguments[1:]
				
				# MODE can be for a user or channel
				if command == 'mode':
					if not is_channel(target):
						command = 'umode'"
				
				# Translate numerics into more readable strings.
				if numeric_events.has_key(command):
					command = numeric_events[command]
				
				# Trigger the event
				self.__event_handler(self, command, prefix, target, arguments)
