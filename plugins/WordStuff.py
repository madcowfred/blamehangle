# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Lookup rhymes, synonyms, or antonyms of words using rhymezone.com

from classes.Plugin import *
from classes.Constants import *

import re
from cStringIO import StringIO

# ---------------------------------------------------------------------------

WORD_RHYME = "WORD_RHYME"
WORD_SYNONYM = "WORD_SYNONYM"
WORD_ANTONYM = "WORD_ANTONYM"

wordbit = "(?P<word>\S+)$"
WORD_RHYME_RE = re.compile("rhyme +" + wordbit)
WORD_SYNONYM_RE = re.compile("synonyms +" + wordbit)
WORD_ANTONYM_RE = re.compile("antonyms +" + wordbit)

RHYME_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=perfect&org1=syl&org2=sl"
SYNONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=syn&org1=let&org2=l"
ANTONYM_URL = "http://www.rhymezone.com/r/rhyme.cgi?Word=%s&typeofrhyme=ant&org1=let&org2=l"

# ---------------------------------------------------------------------------

MAX_WORD_RESULTS = 50

# ---------------------------------------------------------------------------

class WordStuff(Plugin):
	"""
	"rhyme <word>"
	"synonyms <word>"
	"antonyms <word>"

	Lookup words that rhyme, are synonyms, or are antonyms with/of the given
	word, using www.rhymezone.com
	"""

	# -----------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		rhyme_dir = PluginTextEvent(WORD_RHYME, IRCT_PUBLIC_D, WORD_RHYME_RE)
		rhyme_msg = PluginTextEvent(WORD_RHYME, IRCT_MSG, WORD_RHYME_RE)
		syn_dir = PluginTextEvent(WORD_SYNONYM, IRCT_PUBLIC_D, WORD_SYNONYM_RE)
		syn_msg = PluginTextEvent(WORD_SYNONYM, IRCT_MSG, WORD_SYNONYM_RE)
		ant_dir = PluginTextEvent(WORD_ANTONYM, IRCT_PUBLIC_D, WORD_ANTONYM_RE)
		ant_msg = PluginTextEvent(WORD_ANTONYM, IRCT_MSG, WORD_ANTONYM_RE)

		self.register(rhyme_dir, rhyme_msg, syn_dir, syn_msg, ant_dir, ant_msg)
		self.__set_help_msgs()
	
	def __set_help_msgs(self):
		WORD_RHYME_HELP = "'\02rhyme\02 <word>' : Search for other words that rhyme with <word>"
		WORD_SYNONYM_HELP = "'\02synonyms\02 <word>' : Search for words that have the same meaning as <word>"
		WORD_ANTONYM_HELP = "'\02antonyms\02 <word>' : Search for words that have the exact opposite meaning of <word>"

		self.setHelp('words', 'rhyme', WORD_RHYME_HELP)
		self.setHelp('words', 'synonyms', WORD_SYNONYM_HELP)
		self.setHelp('words', 'antonyms', WORD_ANTONYM_HELP)
	
	# -----------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		word = trigger.match.group('word').lower()

		if trigger.name == WORD_RHYME:
			url = RHYME_URL % word
			self.urlRequest(trigger, url)
		elif trigger.name == WORD_SYNONYM:
			url = SYNONYM_URL % word
			self.urlRequest(trigger, url)
		elif trigger.name == WORD_ANTONYM:
			url = ANTONYM_URL % word
			self.urlRequest(trigger, url)
		else:
			errtext = "WordStuff got a bad event: %s" % trigger.name
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------

	# -----------------------------------------------------------------------

	# We heard back from rhymezone. yay!
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		word = trigger.match.group('word').lower()

		# Search through the page for answers
		s = StringIO(page_text)
		
		if trigger.name == WORD_RHYME:
			heading = "Words that rhyme with"
			heading_reply = heading + " \02%s\02 (\02%s\02 results shown): "
			none_reply = "Found no words that rhyme with \02%s\02"
		elif trigger.name == WORD_SYNONYM:
			heading = "Words and phrases that can mean the same thing as"
			heading_reply = "Synonyms for \02%s\02 (\02%s\02 results shown): "
			none_reply = "Found no synonyms of \02%s\02"
		else:
			heading = "Words and phrases that can mean exactly the opposite as"
			heading_reply = "Antonyms for \02%s\02 (\02%s\02 results shown): "
			none_reply = "Found no antonyms of \02%s\02"

		words = ""
		line = s.readline()
		while line:
			line = self.__parse(line)
			if line.startswith(heading):
				# We found some answers. Check to see if it is actually zero
				# answers
				line = self.__parse(s.readline())
				if not line == "(0 results)":
					# There were actually some results
					# the next line is only html
					line = s.readline()

					# The next line is the start of results
					line = self.__parse(s.readline())
					numfound = 0
					wordlist = []
					# loop through all the results
					while not line.startswith("Want more ideas?") \
					and not line.startswith("Commonly searched words are") \
					and not line.endswith(".") \
					and numfound < MAX_WORD_RESULTS:
						if line and not line.endswith(":"):
							# this is a word, not a "2 syllables:" line or
							# a line only containing html tags
							line = line.replace(',', '')
							wordlist.append(line)
							numfound += 1

						# grab the next line and loop	
						line = self.__parse(s.readline())
					
					# We have either run out of answers, or hit the max
					words = ", ".join(wordlist)
					if words.endswith(','):
						words = words[:-1]
					break
			
			# loop
			line = s.readline()
			
		# end of while loop
		if words:
			# we found some answers
			replytext = heading_reply % (word, numfound)
			replytext += words
			self.sendReply(trigger, replytext)
		else:
			# we found nothing!
			replytext = none_reply % word
			self.sendReply(trigger, replytext)
		
		s.close()


	# -----------------------------------------------------------------------
	
	# remove all the HTML tags and the trailing newline from the supplied line
	def __parse(self, text):
		text = re.sub("<.+?>", "", text)
		text = text.replace("&nbsp;", " ")
		if text.endswith("\n"):
			text = text[:-1]
		return text.strip()

	# -----------------------------------------------------------------------
