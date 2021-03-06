# Copyright (c) 2003-2009, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

'Various commands for playing with words.'

import logging
import os
import random
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
BASH_URL = 'http://www.bash.org/?%s'
BASH_SEARCH_URL = 'http://www.bash.org/?search=%s&sort=0&show=25'
URBAN_URL = 'http://www.urbandictionary.com/define.php?term=%s'

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	_HelpSection = 'words'
	
	def setup(self):
		# Cache these results for 12 hours
		self.AcronymCache = SimpleCacheDict(43200)
		self.BashCache = SimpleCacheDict(43200)
		self.UrbanCache = SimpleCacheDict(43200)
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('WordStuff')
		
		# Spell stuff
		if self.Options['spell_bin']:
			if not os.access(self.Options['spell_bin'], os.X_OK):
				tolog = '%s is not executable or not a file, spell command will not work!' % (self.Options['spell_bin'])
				self.logger.warn(tolog)
				
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
		# bash.org
		self.addTextEvent(
			method = self.__Fetch_Bash,
			regexp = r'^bash(?P<n>\s+\S+|)$',
			help = ('bash', '\02bash\02 [findme] : Look up a random quote on bash.org. If [findme] is supplied, we either look up a specific quote (for numbers) or search for that string.'),
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
				url = ACRONYM_URL % (quote(acronym))
				self.urlRequest(trigger, self.__Parse_AcronymFinder, url)
	
	def __Fetch_Antonyms(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = ANTONYM_URL % (word)
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Bash(self, trigger):
		n = trigger.match.group('n').strip()
		if n:
			if n.isdigit():
				line = self.BashCache.get(n)
				if line:
					self.sendReply(trigger, line)
					return
				else:
					url = BASH_URL % (n)
			else:
				n = quote(n)
				url = BASH_SEARCH_URL % (QuoteURL(n))
		else:
			url = BASH_URL % ('random1')
		self.urlRequest(trigger, self.__Parse_Bash, url)
	
	def __Fetch_Rhymes(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = RHYME_URL % (word)
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Synonyms(self, trigger):
		word = quote(trigger.match.group('word').lower())
		url = SYNONYM_URL % (word)
		self.urlRequest(trigger, self.__RhymeZone, url)
	
	def __Fetch_Urban(self, trigger):
		term = trigger.match.group('term').lower()
		if len(term) > 30:
			self.sendReply(trigger, "That's too long!")
		else:
			if term in self.UrbanCache:
				self.__Urban_Reply(trigger)
			else:
				url = URBAN_URL % (QuoteURL(term))
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
		
		self.logger.info(tolog)
	
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
			# Find the definitions
			tds = FindChunks(resp.data, '<td valign="middle" width="84%"', '</td>')
			if not tds:
				self.sendReply(trigger, 'Page parsing failed: tds.')
				return
			
			# Parse the definitions
			defs = []
			for td in tds:
				bits = StripHTML(td)
				if len(bits) == 1:
					defs.append(bits[0])
			
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
	# Parse the output of a bash.org page
	def __Parse_Bash(self, trigger, resp):
		n = trigger.match.group('n').strip()
		
		infos = FindChunks(resp.data, '<p class="quote">', '</p>')
		quotes = FindChunks(resp.data, '<p class="qt">', '</p>')
		
		if not infos or not quotes or len(infos) != len(quotes):
			if 'does not exist.' in resp.data:
				replytext = 'Quote #%s does not exist!' % (n)
			elif 'No results returned.' in resp.data:
				replytext = "No search results for '%s'!" % (n)
			else:
				replytext = 'Page parsing failed: info/quotes.'
			self.sendReply(trigger, replytext)
			return
		
		# Parse the stuff
		lines = []
		for i in range(len(infos)):
			info = infos[i]
			quotelines = StripHTML(quotes[i])
			
			# Join up any split lines
			for j in range(len(quotelines) - 1, 0, -1):
				if quotelines[j][0] not in '([<':
					quotelines[j-1] = '%s %s' % (quotelines[j-1], quotelines[j])
					del quotelines[j]
			
			num = FindChunk(info, '<b>', '</b>')
			quote = ' || '.join(quotelines)
			
			if len(quote) < 400:
				line = '\x02%s\x02. %s' % (num, quote)
				lines.append(line)
				
				self.BashCache[num[1:]] = line
		
		# Spit something out
		if 'search' in resp.url:
			nums = FindChunks(resp.data, '<b>#', '</b>')
			if nums:
				replytext = "Search results for '%s' :: %s" % (n, ', '.join(nums))
			else:
				replytext = "No search results for '%s'!" % (n)
		else:
			if lines:
				replytext = random.choice(lines)
			else:
				if n:
					replytext = 'Quote #%s is too long!' % (n)
				else:
					replytext = 'All quotes were too long!'
		
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
			self.logger.debug(line)
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Urban dictionary got back to us, yo
	def __Parse_Urban(self, trigger, resp):
		term = trigger.match.group('term').lower()
		
		# No match!
		if "isn't defined <a href" in resp.data:
			replytext = "No definitions found for '%s'" % term
			self.sendReply(trigger, replytext)
		
		# Some matches!
		else:
			# Find the definitions
			chunks = FindChunks(resp.data, "<td class='text'", '</tr>')
			if not chunks:
				self.sendReply(trigger, 'Page parsing failed: entries.')
				return
			
			# Parse the definitions
			defs = []
			
			for chunk in chunks:
				out = []
				
				# Find the definition
				definition = FindChunk(chunk, '<div class="definition">', '</div>')
				if not definition:
					continue
				
				# Strip annoying junk
				definition = definition.replace('\r', ' ').replace('\n', ' ')
				definition = StripHTML(definition)[0]
				
				out.append(definition)
				
				# And maybe an example
				example = FindChunk(chunk, "<div class='example'>", '</div>')
				if example:
					# Strip annoying junk
					example = example.replace('\r', ' ').replace('\n', ' ')
					example = StripHTML(example)
					if example:
						out.append(example[0])
				
				# If we got something, add it to the defs list
				if out:
					definition = ' -> '.join(out)
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
		
		self.logger = logging.getLogger('hangle.async_dict')
		
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
			self.logger.warn(tolog)
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
					self.logger.info(tolog)
					self.close()
				
				else:
					tolog = "DICT server gave me an unknown response: %s" % line
					self.logger.info(tolog)
			
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
					replytext = " ".join(self.__def[1:])
					self.parent.sendReply(self.trigger, replytext)
					
					self.quit()
				
				# No match!
				elif line.startswith('552 '):
					replytext = 'No match found for "%s"' % (self.word)
					self.parent.sendReply(self.trigger, replytext)
					
					self.quit()
			
			# Getting a word
			elif self.state == 2:
				if line == '.':
					self.state = 1
				else:
					self.__def.append(line.strip())
	
	def handle_close(self):
		self.close()
	
	# Shortcut, it gets used twice!
	def quit(self):
		self.send('QUIT\r\n')

# ---------------------------------------------------------------------------
