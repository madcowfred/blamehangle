# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Various commands for playing with words.'

import os
import re
import socket
import time
from urllib import quote

from classes.async_buffered import buffered_dispatcher
from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin
from classes.SimpleCacheDict import SimpleCacheDict

# ---------------------------------------------------------------------------

ANTONYM_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=ant&org1=let&org2=l'
RHYME_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=perfect&org1=let&org2=sl'
SYNONYM_URL = 'http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=syn&org1=syl&org2=l'

# Match the results line
RESULTS_RE = re.compile(r'^\((\d+) res')
# Match a proper word
WORD_RE = re.compile(r'^([A-Za-z\- ]+)\,?$')

# Limit the number of results we come up with
RHYMEZONE_LIMIT = 40

# ---------------------------------------------------------------------------

ACRONYM_URL = 'http://www.acronymfinder.com/af-query.asp?String=exact&Acronym=%s&Find=Find'
URBAN_URL = 'http://www.urbandictionary.com/define.php?term=%s&r=f'

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	_HelpSection = 'words'
	
	def setup(self):
		# Cache these results for 12 hours
		self.AcronymCache = SimpleCacheDict(43200)
		self.UrbanCache = SimpleCacheDict(43200)
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('WordStuff')
		
		# Spell stuff
		if self.Options['spell_bin']:
			if not os.access(self.Options['spell_bin'], os.X_OK):
				tolog = '%s is not executable or not a file, spell command will not work!' % (self.Options['spell_bin'])
				self.putlog(LOG_WARNING, tolog)
				
				self.__spell_bin = None
			else:
				self.__spell_bin = '%s -a -S' % (self.Options['spell_bin'])
	
	# -----------------------------------------------------------------------
	
	def register(self):
		# AcronymFinder
		self.addTextEvent(
			method = self.__Fetch_Acronyms,
			regexp = r'^acronyms?(?P<n>\s+\d+\s+|\s+)(?P<acronym>\S+)$',
			help = ('acronyms', '\02acronyms\02 [n] <acronym> : Look up <acronym>, possibly getting definition [n].'),
		)
		# RhymeZone
		self.addTextEvent(
			method = self.__Fetch_Antonyms,
			regexp = r'antonyms? (?P<word>\S+)$',
			help = ('antonyms', '\02antonyms\02 <word> : Search for words that have the opposite meaning to <word>.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Rhymes,
			regexp = r'rhymes? (?P<word>\S+)$',
			help = ('rhymes', '\02rhymes\02 <word> : Search for words that rhyme with <word>.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Synonyms,
			regexp = r'synonyms? (?P<word>\S+)$',
			help = ('synonyms', '\02synonyms\02 <word> : Search for words that have the same meaning of <word>.'),
		)
		# UrbanDictionary
		self.addTextEvent(
			method = self.__Fetch_Urban,
			regexp = r'^urban(?P<n>\s+\d+\s+|\s+)(?P<term>.+)$',
			help = ('urban', '\02urban\02 [n] <term> : Look up <term> on urbandictionary.com, possibly getting definition [n].'),
		)
		# DICT
		self.addTextEvent(
			method = self.__DICT,
			regexp = r'^dict (?P<word>\S+)$',
			help = ('dict', '\02dict\02 <word> : Look up the dictionary meaning of a word.'),
		)
		# Spell
		self.addTextEvent(
			method = self.__Spell,
			regexp = r'^spell\s+(?P<word>\S+)$',
			help = ('spell', '\02spell\02 <word> : Check spelling of a word.'),
		)
	
	# -----------------------------------------------------------------------
	
	def __Fetch_Acronyms(self, trigger):
		acronym = trigger.match.group('acronym').upper()
		if len(acronym) > 20:
			self.sendReply(trigger, "That's too long!")
		else:
			if acronym in self.AcronymCache:
				self.__Acronym_Reply(trigger)
			else:
				url = ACRONYM_URL % QuoteURL(acronym)
				self.urlRequest(trigger, self.__Parse_AcronymFinder, url)
	
	def __Fetch_Antonyms(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = ANTONYM_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Rhymes(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = RHYME_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Synonyms(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = SYNONYM_URL % word
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Urban(self, trigger):
		term = trigger.match.group('term').lower()
		if len(term) > 30:
			self.sendReply(trigger, "That's too long!")
		
		else:
			if term in self.UrbanCache:
				self.__Urban_Reply(trigger)
			else:
				url = URBAN_URL % QuoteURL(term)
				self.urlRequest(trigger, self.__Parse_Urban, url)
	
	# -----------------------------------------------------------------------
	
	def __DICT(self, trigger):
		word = trigger.match.group('word').lower()
		if len(word) > 30:
			tolog = 'Dictionary: %s asked me to look up a very long word!' % (trigger.userinfo.nick)
			self.sendReply(trigger, "That's too long!")
		
		else:
			tolog = 'Dictionary: %s asked me to look up "%s"' % (trigger.userinfo.nick, word)
			async_dict(self, trigger)
		
		self.putlog(LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Parse the output of an AcronymFinder page
	def __Parse_AcronymFinder(self, trigger, resp):
		acronym = trigger.match.group('acronym').upper()
		
		# No match!
		if resp.data.find('was not found in the database') >= 0:
			replytext = "No definitions found for '%s'" % (acronym)
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			# Find the definition block
			chunk = FindChunk(resp.data, '<table border="0" cellspacing="0" cellpadding="4" width="80%">', '</table>')
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: definition table.')
				return
			
			# Find the rows
			trs = FindChunks(chunk, '<tr bgcolor', '</tr>')
			if not trs:
				self.sendReply(trigger, 'Page parsing failed: table rows.')
				return
			
			# Parse the definitions
			defs = []
			
			for tr in trs:
				bits = StripHTML(tr)
				if len(bits) == 2:
					defs.append(bits[1])
			
			# If we got some definitions, add them to the cache and spit
			# something out
			if defs:
				self.AcronymCache[acronym] = defs
				self.__Acronym_Reply(trigger)
			else:
				replytext = 'Page parsing failed: definition.'
				self.sendReply(trigger, replytext)
	
	# Spit out something from our AcronymFinder cache
	def __Acronym_Reply(self, trigger):
		try:
			n = int(trigger.match.group('n'))
		except ValueError:
			n = 1
		acronym = trigger.match.group('acronym').upper()
		
		# See if they're being stupid
		defs = self.AcronymCache.get(acronym)
		if defs is None:
			replytext = "Cached entry for %s has just expired!" % acronym
		else:
			numdefs = len(defs)
			if n > numdefs:
				replytext = "There are only %d definitions for '%s'!"% (numdefs, acronym)
			else:
				replytext = "%s \2[\02%d/%d\02]\02 :: %s" % (acronym, n, numdefs, defs[n-1])
		
		# Spit it out
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the output of a RhymeZone page
	def __RhymeZone(self, trigger, resp):
		word = trigger.match.group('word').lower()
		
		# If the word wasn't found at all, we don't need to do anything else
		if resp.data.find('was not found in this dictionary') >= 0:
			replytext = "'%s' was not found in the dictionary." % (word)
			self.sendReply(trigger, replytext)
			return
		
		# Set up some stuff here
		if trigger.name == '__Fetch_Antonyms':
			findme = "Words and phrases that can mean exactly the opposite as"
			some_reply = "Antonyms for '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no antonyms of '%s'"
		
		if trigger.name == '__Fetch_Rhymes':
			findme = 'Words that rhyme with'
			some_reply = "Words that rhyme with '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no words that rhyme with '%s'"
		
		elif trigger.name == '__Fetch_Synonyms':
			findme = "Words and phrases that can mean the same thing as"
			some_reply = "Synonyms for '%s' (\02%s\02 results shown): %s"
			none_reply = "Found no synonyms of '%s'"
		
		# Search through the page for answers
		words = []
		
		chunk = FindChunk(resp.data, findme, '<center>')
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
		if not self.__spell_bin:
			self.sendReply(trigger, 'spell is broken until my owner fixes it.')
			return
		
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
	def __Parse_Urban(self, trigger, resp):
		term = trigger.match.group('term').lower()
		
		# No match!
		if resp.data.find('No definitions found') >= 0:
			replytext = "No definitions found for '%s'" % term
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			# Find the definitions
			chunks = FindChunks(resp.data, '<div class="text">', '</td>')
			if not chunks:
				self.sendReply(trigger, 'Page parsing failed: divs.')
				return
			
			# Parse the definitions
			defs = []
			
			for chunk in chunks:
				out = []
				
				# We only want the first line
				definition = FindChunk(chunk, '<div class="def">', '</div>')
				if not definition:
					self.sendReply(trigger, 'Page parsing failed: def.')
					return
				
				# Strip annoying junk
				definition = definition.replace('\r', '').replace('\n', '')
				definition = StripHTML(definition)[0]
				out.append(definition)
				
				# And maybe an example
				example = FindChunk(chunk, '<div class="example">', '</div>')
				if example:
					# Strip annoying junk
					example = example.replace('\r', '').replace('\n', '')
					example = '"%s"' % (example)
					example = StripHTML(example)[0]
					
					out.append(example)
				
				# If we got something, add it to the defs list
				if out:
					definition = ' '.join(out)
					defs.append(definition)
			
			# If we got some definitions, add them to the cache and spit
			# something out
			if defs:
				self.UrbanCache[term] = defs
				self.__Urban_Reply(trigger)
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
		defs = self.UrbanCache.get(term)
		if defs is None:
			replytext = "Cached entry for %s has just expired!" % (term)
		else:
			numdefs = len(defs)
			if n > numdefs:
				replytext = "There are only %d definitions for '%s'!"% (numdefs, term)
			else:
				replytext = "%s \2[\02%d/%d\02]\02 :: %s" % (term, n, numdefs, defs[n-1])
		
		# Spit it out
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
# Blah to evil people who can't agree on line seperators :)
_linesep_regexp = re.compile('\r?\n')

class async_dict(buffered_dispatcher):
	def __init__(self, parent, trigger):
		buffered_dispatcher.__init__(self)
		
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
			self.connect((self.parent.Options['dict_host'], self.parent.Options['dict_port']))
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
					
					tosend = 'DEFINE %s %s\r\n' % (self.parent.Options['dict_dict'], self.word)
					self.send(tosend)
				
				elif line.startswith('530 '):
					tolog = "DICT server '%s' says: %s" % (self.parent.Options['dict_host'], line)
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
