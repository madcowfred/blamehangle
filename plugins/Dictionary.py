# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Implements a DICT protocol (RFC 2229) client, aiee.

import asyncore
import re
import socket

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

DICTIONARY_DICT = 'DICTIONARY_DICT'
DICT_RE = re.compile(r'^dict (?P<word>\S+)$')
DICT_HELP = '\02dict\02 <word> : Look up the dictionary meaning of a word.'

# ---------------------------------------------------------------------------

class Dictionary(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self._host = self.Config.get('Dictionary', 'host')
		self._port = self.Config.getint('Dictionary', 'port')
		self._dict = self.Config.get('Dictionary', 'dict')
	
	def _message_PLUGIN_REGISTER(self, message):
		dict_dir = PluginTextEvent(DICTIONARY_DICT, IRCT_PUBLIC_D, DICT_RE)
		dict_msg = PluginTextEvent(DICTIONARY_DICT, IRCT_MSG, DICT_RE)
		self.register(dict_dir, dict_msg)
		
		self.setHelp('dict', 'dict', DICT_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == DICTIONARY_DICT:
			word = trigger.match.group('word').lower()
			if len(word) > 30:
				tolog = 'Dictionary: %s asked me to look up a very long word!' % (trigger.userinfo.nick)
				
				self.sendReply(trigger, "That's too long!")
			
			else:
				tolog = 'Dictionary: %s asked me to look up "%s"' % (trigger.userinfo.nick, word)
				
				async_dict(self, trigger)
			
			self.putlog(LOG_ALWAYS, tolog)


# ---------------------------------------------------------------------------
# Blah to evil people who can't agree on line seperators :)
_linesep_regexp = re.compile('\r?\n')

class async_dict(asyncore.dispatcher_with_send):
	
	def __init__(self, parent, trigger):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.__read_buf = ''
		self.state = 0
		
		self.parent = parent
		self.trigger = trigger
		
		self.word = trigger.match.group('word').lower()
		
		# Create the socket
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		
		# Try to connect. It seems this will blow up if it can't resolve the
		# host.
		try:
			self.connect((self.parent._host, self.parent._port))
		except socket.gaierror, msg:
			tolog = "Error while connecting to DICT server: %s - %s" % (self.url, msg)
			self.parent.putlog(LOG_WARNING, tolog)
			self.close()
	
	# We don't have to do anything when it connects
	def handle_connect(self):
		pass
	
	def handle_read(self):
		self.__read_buf += self.recv(1024)
		
		# Split the data into lines. The last line is either incomplete or
		# empty, so we save it for later.
		lines = _linesep_regexp.split(self.__read_buf)
		self.__read_buf = lines[-1]
		
		# See what the lines have
		for line in lines[:-1]:
			# Just connected
			if self.state == 0:
				if line.startswith('220 '):
					self.state = 1
					
					tosend = 'DEFINE %s %s\r\n' % (self.parent._dict, self.word)
					self.send(tosend)
				
				elif line.startswith('530 '):
					tolog = "DICT server '%s' says: %s" % (self.parent._host, line)
					self.putlog(tolog)
					self.close()
				
				else:
					print 'wtf? %s' % line
			
			# Asked for a word
			elif self.state == 1:
				# One or more definitions found, yay
				if line.startswith('150 '):
					pass
				
				# A definition is coming
				elif line.startswith('151 '):
					self.state = 2
					self.__def = []
				
				# Goodbye
				elif line.startswith('221 '):
					self.close()
				
				# A definition has finished
				elif line.startswith('250 '):
					tolog = 'Definition found!'
					self.putlog(tolog)
					
					replytext = " ".join(self.__def[1:])
					self.parent.sendReply(self.trigger, replytext)
					
					self.quit()
				
				# No match!
				elif line.startswith('552 '):
					replytext = 'No match found for "%s"' % (self.word)
					self.parent.sendReply(self.trigger, replytext)
					
					self.putlog(replytext)
					
					self.quit()
			
			# Getting a word
			elif self.state == 2:
				if line == '.':
					self.state = 1
				else:
					self.__def.append(line.strip())
	
	def handle_close(self):
		self.close()
	
	# Log stuff nicely
	def putlog(self, text):
		tolog = 'Dictionary: %s' % (text)
		self.parent.putlog(LOG_ALWAYS, tolog)
	
	# Shortcut, it gets used twice!
	def quit(self):
		self.send('QUIT\r\n')
