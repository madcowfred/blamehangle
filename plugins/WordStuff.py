# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Lookup rhymes, synonyms, or antonyms of words using rhymezone.com
# Look up dictionary meanings via the DICT protocol (RFC 2229)

import asyncore
import os
import re
import socket
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

wordbit = "(?P<word>\S+)$"

WORD_ANTONYM = "WORD_ANTONYM"
ANTONYM_HELP = "'\02antonyms\02 <word>' : Search for words that have the exact opposite meaning of <word>"
ANTONYM_RE = re.compile("antonyms? +" + wordbit)
ANTONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=ant&org1=let&org2=l"

WORD_RHYME = "WORD_RHYME"
RHYME_HELP = "'\02rhyme\02 <word>' : Search for other words that rhyme with <word>"
RHYME_RE = re.compile("rhyme +" + wordbit)
RHYME_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=perfect&org1=let&org2=sl"

WORD_SYNONYM = "WORD_SYNONYM"
SYNONYM_HELP = "'\02synonyms\02 <word>' : Search for words that have the same meaning as <word>"
SYNONYM_RE = re.compile("synonyms? +" + wordbit)
SYNONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=syn&org1=let&org2=l"

# Match the results line
RESULTS_RE = re.compile(r'^\((\d+) res')
# Match a proper word
WORD_RE = re.compile(r'^([A-Za-z\-]+)\,?$')

# Limit the number of results we come up with
RHYMEZONE_LIMIT = 40

# ---------------------------------------------------------------------------

WORD_DICT = 'WORD_DICT'
DICT_HELP = '\02dict\02 <word> : Look up the dictionary meaning of a word.'
DICT_RE = re.compile(r'^dict (?P<word>\S+)$')

# ---------------------------------------------------------------------------

WORD_SPELL = 'WORD_SPELL'
SPELL_HELP = '\02spell\02 <word> : Check spelling of a word.'
SPELL_RE = re.compile('^spell\s+(?P<word>\S+)$')

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	def setup(self):
		self.__spell_bin = ''
		
		self.rehash()
	
	def rehash(self):
		# DICT stuff
		self._dict_host = self.Config.get('WordStuff', 'dict_host')
		self._dict_port = self.Config.getint('WordStuff', 'dict_port')
		self._dict_dict = self.Config.get('WordStuff', 'dict_dict')
		
		# Spell stuff
		bin	= self.Config.get('WordStuff', 'spell_bin')
		if bin:
			if not os.access(bin, os.X_OK):
				tolog = '%s is not executable or not a file, spell command will not work!' % bin
				self.putlog(LOG_WARNING, tolog)
			
			else:
				self.__spell_bin = '%s -a -S' % bin
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		# RhymeZone
		self.setTextEvent(WORD_ANTONYM, ANTONYM_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WORD_RHYME, RHYME_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WORD_SYNONYM, SYNONYM_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# DICT
		self.setTextEvent(WORD_DICT, DICT_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# Spell
		self.setTextEvent(WORD_SPELL, SPELL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		
		self.registerEvents()
		
		self.setHelp('words', 'antonyms', ANTONYM_HELP)
		self.setHelp('words', 'rhyme', RHYME_HELP)
		self.setHelp('words', 'synonyms', SYNONYM_HELP)
		self.setHelp('words', 'dict', DICT_HELP)
		self.setHelp('words', 'spell', SPELL_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		word = quote(trigger.match.group('word').lower())
		
		if trigger.name == WORD_ANTONYM:
			url = ANTONYM_URL % word
			self.urlRequest(trigger, url)
		
		elif trigger.name == WORD_RHYME:
			url = RHYME_URL % word
			self.urlRequest(trigger, url)
		
		elif trigger.name == WORD_SYNONYM:
			url = SYNONYM_URL % word
			self.urlRequest(trigger, url)
		
		elif trigger.name == WORD_DICT:
			word = trigger.match.group('word').lower()
			if len(word) > 30:
				tolog = 'Dictionary: %s asked me to look up a very long word!' % (trigger.userinfo.nick)
				
				self.sendReply(trigger, "That's too long!")
			
			else:
				tolog = 'Dictionary: %s asked me to look up "%s"' % (trigger.userinfo.nick, word)
				
				async_dict(self, trigger)
			
			self.putlog(LOG_ALWAYS, tolog)
		
		elif trigger.name == WORD_SPELL:
			if self.__spell_bin:
				self.__Spell(trigger)
			else:
				self.sendReply(trigger, 'spell is broken until my owner fixes it.')
				return
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name in (WORD_ANTONYM, WORD_RHYME, WORD_SYNONYM):
			self.__RhymeZone(trigger, page_text)
	
	# -----------------------------------------------------------------------
	
	def __RhymeZone(self, trigger, page_text):
		word = trigger.match.group('word').lower()
		
		# If the word wasn't found at all, we don't need to do anything else
		if page_text.find('was not found in this dictionary') >= 0:
			replytext = "'%s' was not found in the dictionary." % (word)
			self.sendReply(trigger, replytext)
			return
		
		# Set up some stuff here
		if trigger.name == WORD_ANTONYM:
			findme = "Words and phrases that can mean exactly the opposite as"
			some_reply = "Antonyms for '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no antonyms of '%s'"
		
		if trigger.name == WORD_RHYME:
			findme = 'Words that rhyme with'
			some_reply = "Words that rhyme with '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no words that rhyme with '%s'"
		
		elif trigger.name == WORD_SYNONYM:
			findme = "Words and phrases that can mean the same thing as"
			some_reply = "Synonyms for '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no synonyms of '%s'"
		
		# Search through the page for answers
		words = []
		
		chunk = FindChunk(page_text, findme, '<center>')
		if chunk:
			lines = StripHTML(chunk)
			
			# See if we got any results
			m = RESULTS_RE.search(lines[1])
			if m:
				results = int(m.group(1))
			else:
				results = 0
			
			# If we have some results, find all words that match our regexp
			if results > 0:
				for line in lines[2:]:
					m = WORD_RE.match(line)
					if m:
						words.append(m.group(1))
			
			# If we found some words, spit them out
			if words:
				words.sort()
				if len(words) > RHYMEZONE_LIMIT:
					results = RHYMEZONE_LIMIT
					words = words[:RHYMEZONE_LIMIT]
				
				replytext = some_reply % (word, results, ', '.join(words))
			
			# If we didn't, spit out a sad message
			else:
				replytext = none_reply % (word)
			
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def __Spell(self, trigger):
		word = trigger.match.group('word')
		
		# Returns 
		p_in, p_out = os.popen2(self.__spell_bin)
		
		towrite = '%s\n' % word
		p_in.write(towrite)
		p_in.flush()
		p_in.close()
		
		data = p_out.readlines()
		p_out.close()
		
		# We only care about the second line
		line = data[1]
		
		# If it starts with '*', we were right! And if it starts with +, we
		# were also right :|
		if line.startswith('*') or line.startswith('+'):
			replytext = "'%s' is probably spelled correctly." % word
		# If it starts with '#', we were pretty far wrong!
		elif line.startswith('#'):
			replytext = "'%s' isn't even CLOSE to being a real word!" % word
		# We weren't right, but we might be close
		elif line.startswith('&'):
			words = line.split(None, 4)[4]
			replytext = "Possible matches for '%s': %s" % (word, words)
		# We weren't right, but we may have a mangled form of a word
		elif line.startswith('?'):
			mangled = line.split(None, 4)[4]
			plus = mangled.find('+')
			minus = mangled.find('-')
			if plus >= 0 and plus < minus:
				replytext = "'%s' is probably a mangled form of '%s'" % (word, mangled[:plus])
			elif minus >= 0 and minus < plus:
				replytext = "'%s' is probably a mangled form of '%s'" % (word, mangled[:minus])
		# Err?
		else:
			replytext = 'Failed to parse [ai]spell output.'
			self.putlog(LOG_DEBUG, line)
		
		self.sendReply(trigger, replytext)

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
			self.connect((self.parent._dict_host, self.parent._dict_port))
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
					
					tosend = 'DEFINE %s %s\r\n' % (self.parent._dict_dict, self.word)
					self.send(tosend)
				
				elif line.startswith('530 '):
					tolog = "DICT server '%s' says: %s" % (self.parent._dict_host, line)
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

# ---------------------------------------------------------------------------
