# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Various commands for playing with words.'

import asyncore
import os
import re
import socket
import time
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

wordbit = '(?P<word>\S+)$'

WORD_ANTONYM = 'WORD_ANTONYM'
ANTONYM_HELP = '\02antonyms\02 <word> : Search for words that have the exact opposite meaning of <word>.'
ANTONYM_RE = re.compile("antonyms? +" + wordbit)
ANTONYM_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=ant&org1=let&org2=l'

WORD_RHYME = 'WORD_RHYME'
RHYME_HELP = '\02rhyme\02 <word> : Search for words that rhyme with <word>.'
RHYME_RE = re.compile('rhyme +' + wordbit)
RHYME_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=perfect&org1=let&org2=sl'

WORD_SYNONYM = 'WORD_SYNONYM'
SYNONYM_HELP = '\02synonyms\02 <word> : Search for words that have the same meaning as <word>.'
SYNONYM_RE = re.compile("synonyms? +" + wordbit)
SYNONYM_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=syn&org1=let&org2=l'

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

WORD_URBAN = 'WORD_URBAN'
URBAN_HELP = '\02urban\02 [n] <term> : Look up <term> on urbandictionary.com, possibly getting definition [n].'
URBAN_RE = re.compile('^urban(?P<n>\s+\d+\s+|\s+)(?P<term>.+)$')
URBAN_URL = 'http://www.urbandictionary.com/define.php?term=%s'

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	def setup(self):
		self.__spell_bin = None
		
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
				
				self.__spell_bin = None
			
			else:
				self.__spell_bin = '%s -a -S' % bin
		
		# Urban stuff
		self.__Urban_Defs = {}
	
	# -----------------------------------------------------------------------
	
	def register(self):
		# RhymeZone
		self.setTextEvent(WORD_ANTONYM, ANTONYM_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WORD_RHYME, RHYME_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WORD_SYNONYM, SYNONYM_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# DICT
		self.setTextEvent(WORD_DICT, DICT_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# Spell
		self.setTextEvent(WORD_SPELL, SPELL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# UrbanDictionary
		self.setTextEvent(WORD_URBAN, URBAN_RE, IRCT_PUBLIC_D, IRCT_MSG)
		
		self.registerEvents()
		
		self.setHelp('words', 'antonyms', ANTONYM_HELP)
		self.setHelp('words', 'rhyme', RHYME_HELP)
		self.setHelp('words', 'synonyms', SYNONYM_HELP)
		self.setHelp('words', 'dict', DICT_HELP)
		self.setHelp('words', 'spell', SPELL_HELP)
		self.setHelp('words', 'urban', URBAN_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _trigger_WORD_ANTONYM(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = ANTONYM_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def _trigger_WORD_RHYME(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = RHYME_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def _trigger_WORD_SYNONYM(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = SYNONYM_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def _trigger_WORD_DICT(self, trigger):
		word = trigger.match.group('word').lower()
		if len(word) > 30:
			tolog = 'Dictionary: %s asked me to look up a very long word!' % (trigger.userinfo.nick)
			self.sendReply(trigger, "That's too long!")
		
		else:
			tolog = 'Dictionary: %s asked me to look up "%s"' % (trigger.userinfo.nick, word)
			async_dict(self, trigger)
		
		self.putlog(LOG_ALWAYS, tolog)
		
	def _trigger_WORD_SPELL(self, trigger):
		if self.__spell_bin:
			self.__Spell(trigger)
		else:
			self.sendReply(trigger, 'spell is broken until my owner fixes it.')
	
	def _trigger_WORD_URBAN(self, trigger):
		term = trigger.match.group('term').lower()
		if len(term) > 30:
			self.sendReply(trigger, "That's too long!")
		
		else:
			if term in self.__Urban_Defs:
				# Older than 12 hours, kill it
				if (time.time() - self.__Urban_Defs[term]['time']) > 43200:
					del self.__Urban_Defs[term]
				# Use the cached one
				else:
					self.__Urban_Reply(trigger)
					return
			
			# Fetch a new one
			url = URBAN_URL % QuoteURL(term)
			self.urlRequest(trigger, self.__Urban, url)
	
	# -----------------------------------------------------------------------
	# Parse the output of a RhymeZone page
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
	# Look up the spelling of a word using ispell or (preferably) aspell
	def __Spell(self, trigger):
		word = trigger.match.group('word').lower()
		
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
	
	# -----------------------------------------------------------------------
	# Urban dictionary got back to us, yo
	def __Urban(self, trigger, page_text):
		term = trigger.match.group('term').lower()
		
		# No match!
		if page_text.find('No definitions found') >= 0:
			replytext = "No definitions found for '%s'" % term
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			# Find the definitions
			chunks = FindChunks(page_text, '<blockquote>', '</blockquote>')
			if not chunks:
				self.sendReply(trigger, 'Page parsing failed: blockquotes.')
				return
			
			# Parse the definitions
			defs = []
			
			for chunk in chunks:
				out = []
				
				# Find each line
				ps = FindChunks(chunk, '<p>', '</p>')
				if not ps:
					self.sendReply(trigger, 'Page parsing failed: lines.')
					return
				
				for p in ps:
					# If it's an empty quote, skip it
					if p == '<i></i>':
						continue
					
					# Remove annoying <br>s
					p = p.replace('\r<br />\n', ' ')
					
					# If it's a quote, make it look like one
					quote = FindChunk(p, '<i>', '</i>')
					if quote:
						p = '"%s"' % (quote)
					
					# Get rid of evil links
					p = StripHTML(p)[0]
					
					# Stick it in the list
					out.append(p)
				
				# If we got something, add it to the defs list
				if out:
					definition = ' '.join(out)
					defs.append(definition)
			
			# If we got some definitions, add them to the cache and spit
			# something out
			if defs:
				self.__Urban_Defs[term] = {
					'time': time.time(),
					'defs': defs
				}
				
				self.__Urban_Reply(trigger)
			
			# If not, cry
			else:
				replytext = 'Page parsing failed: definition.'
				self.sendReply(trigger, replytext)
	
	# Spit out something from our UD cache
	def __Urban_Reply(self, trigger):
		try:
			n = int(trigger.match.group('n'))
		except ValueError:
			n = 1
		term = trigger.match.group('term').lower()
		
		# See if they're being stupid
		numdefs = len(self.__Urban_Defs[term]['defs'])
		
		if n > numdefs:
			replytext = "There are only %d definitions for '%s'!"% (numdefs, term)
		
		# Guess they're not
		else:
			replytext = "%s \2[\02%d/%d\02]\02 :: %s" % (term, n, numdefs, self.__Urban_Defs[term]['defs'][n-1])
		
		# Spit it out
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
					self.putlog(LOG_ALWAYS, tolog)
					self.close()
				
				else:
					tolog = "DICT server gave me an unknown response: %s" % line
					self.putlog(LOG_ALWAYS, tolog)
			
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
