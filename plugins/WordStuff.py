# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Lookup rhymes, synonyms, or antonyms of words using rhymezone.com

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

wordbit = "(?P<word>\S+)$"

WORD_RHYME = "WORD_RHYME"
RHYME_RE = re.compile("rhyme +" + wordbit)
RHYME_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=perfect&org1=let&org2=sl"
RHYME_HELP = "'\02rhyme\02 <word>' : Search for other words that rhyme with <word>"

WORD_SYNONYM = "WORD_SYNONYM"
SYNONYM_RE = re.compile("synonyms +" + wordbit)
SYNONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=syn&org1=let&org2=l"
SYNONYM_HELP = "'\02synonyms\02 <word>' : Search for words that have the same meaning as <word>"

WORD_ANTONYM = "WORD_ANTONYM"
ANTONYM_RE = re.compile("antonyms +" + wordbit)
ANTONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=ant&org1=let&org2=l"
ANTONYM_HELP = "'\02antonyms\02 <word>' : Search for words that have the exact opposite meaning of <word>"

# Match the results line
RESULTS_RE = re.compile(r'^\((\d+) res')
# Match a proper word
WORD_RE = re.compile(r'^([A-Za-z\-]+)\,?$')

# ---------------------------------------------------------------------------

MAX_WORD_RESULTS = 50

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	"""
	Lookup words that rhyme, are synonyms, or are antonyms with/of the given
	word, using www.rhymezone.com
	"""
	
	def _message_PLUGIN_REGISTER(self, message):
		ant_dir = PluginTextEvent(WORD_ANTONYM, IRCT_PUBLIC_D, ANTONYM_RE)
		ant_msg = PluginTextEvent(WORD_ANTONYM, IRCT_MSG, ANTONYM_RE)
		rhyme_dir = PluginTextEvent(WORD_RHYME, IRCT_PUBLIC_D, RHYME_RE)
		rhyme_msg = PluginTextEvent(WORD_RHYME, IRCT_MSG, RHYME_RE)
		syn_dir = PluginTextEvent(WORD_SYNONYM, IRCT_PUBLIC_D, SYNONYM_RE)
		syn_msg = PluginTextEvent(WORD_SYNONYM, IRCT_MSG, SYNONYM_RE)
		self.register(ant_dir, ant_msg, rhyme_dir, rhyme_msg, syn_dir, syn_msg)
		
		self.setHelp('words', 'antonyms', ANTONYM_HELP)
		self.setHelp('words', 'rhyme', RHYME_HELP)
		self.setHelp('words', 'synonyms', SYNONYM_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		word = quote(trigger.match.group('word').lower())
		
		if trigger.name == WORD_ANTONYM:
			url = ANTONYM_URL % word
		elif trigger.name == WORD_RHYME:
			url = RHYME_URL % word
		elif trigger.name == WORD_SYNONYM:
			url = SYNONYM_URL % word
		
		self.urlRequest(trigger, url)
	
	# We heard back from rhymezone. yay!
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
						print 'match! %s' % (m.group(1))
						words.append(m.group(1))
			
			# If we found some words, spit them out
			if words:
				words.sort()
				replytext = some_reply % (word, results, ', '.join(words))
			# If we didn't, spit out a sad message
			else:
				replytext = none_reply % (word)
			
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
