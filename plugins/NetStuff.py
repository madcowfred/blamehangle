# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Miscellaneous commands for various network things.'

import os
import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class NetStuff(Plugin):
	def setup(self):
		self.__ccTLDs = {}
		
		filename = os.path.join('data', 'cctlds')
		try:
			cctld_file = open(filename, 'r')
		except IOError:
			self.putlog(LOG_WARNING, "Can't find data/cctlds!")
			return
		
		for line in cctld_file:
			line = line.strip()
			if not line:
				continue
			
			cctld, country = line.split(None, 1)
			self.__ccTLDs[cctld] = country
		
		cctld_file.close()
	
	def register(self):
		self.addTextEvent(
			method = self.__ccTLD,
			regexp = re.compile('^cctld (.+)$'),
			help = ('net', 'cctld', '\02cctld\02 <code> OR <country> : Look up the country for <code>, or search for the ccTLD for <country>.'),
		)
	
	# ---------------------------------------------------------------------------
	# Someone wants to look up a ccTLD!
	def __ccTLD(self, trigger):
		findme = trigger.match.group(1).lower()
		
		# Evil people should die
		if len(findme) <= 1:
			self.sendReply(trigger, "That's too short!")
			return
		if len(findme) > 20:
			self.sendReply(trigger, "That's too long!")
			return
		
		# Two letters should be a country code
		if len(findme) == 2:
			findme = '.%s' % findme
		
		# Country code time
		if len(findme) == 3 and findme.startswith('.'):
			if findme in self.__ccTLDs:
				replytext = '%s is the ccTLD for %s' % (findme, self.__ccTLDs[findme])
			else:
				replytext = 'No such ccTLD: %s' % findme
		
		# Country name
		else:
			matches = [c for c in self.__ccTLDs.items() if c[1].lower().find(findme) >= 0]
			if matches:
				if len(matches) == 1:
					replytext = '%s is the ccTLD for %s' % (matches[0][0], matches[0][1])
				else:
					parts = []
					for cctld, country in matches:
						part = '\02[\02%s: %s\02]\02' % (cctld, country)
						parts.append(part)
					replytext = ' '.join(parts)
			else:
				replytext = "No matches found for '%s'" % (findme)
		
		# Spit something out
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
