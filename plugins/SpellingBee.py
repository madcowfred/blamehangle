# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Spells things.

import os
import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

BEE_SPELL = 'BEE_SPELL'
SPELL_HELP = "'\02spell\02' <word> : Check spelling for <word>"
SPELL_RE = re.compile('^spell\s+(?P<word>\S+)$')

# ---------------------------------------------------------------------------

class SpellingBee(Plugin):
	def setup(self):
		self.__bin = ''
		self.__setup_config()

	def __setup_config(self):
		bin	= self.Config.get('SpellingBee', 'bin_location')
		if bin:
			if not os.path.isfile(bin):
				tolog = '%s is not a file, SpellingBee will not work as expected!' % bin
				self.putlog(LOG_WARNING, tolog)
			
			elif not os.access(bin, os.X_OK):
				tolog = '%s is not executable, SpellingBee will not work as expected!' % bin
				self.putlog(LOG_WARNING, tolog)
			
			else:
				self.__bin = '%s -a -S' % bin
	
	def _message_REQ_REHASH(self, message):
		self.__setup_config()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		if self.__bin:
			spell_dir = PluginTextEvent(BEE_SPELL, IRCT_PUBLIC_D, SPELL_RE)
			spell_msg = PluginTextEvent(BEE_SPELL, IRCT_MSG, SPELL_RE)
			self.register(spell_dir, spell_msg)
			self.setHelp('words', 'spell', SPELL_HELP)
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == BEE_SPELL:
			self.__Spell(trigger)
	
	# -----------------------------------------------------------------------
	
	def __Spell(self, trigger):
		word = trigger.match.group('word')
		
		# Returns 
		p_in, p_out = os.popen2(self.__bin)
		
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
		# If it starts with '#', we were pretty wrong!
		elif line.startswith('#'):
			replytext = "'%s' isn't even CLOSE to being a real word!" % word
		# We weren't right, but we might be close
		elif line.startswith('&'):
			words = line.split(None, 4)[4]
			replytext = "Possible matches for '%s': %s" % (word, words)
		# Err?
		else:
			replytext = 'I have no idea what just happened.'
			self.putlog(LOG_DEBUG, line)
		
		self.sendReply(trigger, replytext)
