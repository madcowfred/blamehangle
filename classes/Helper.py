# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Give help on using blamehangle's irc commands

import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

HELPER_HELP = 'HELPER_HELP'
HELP_RE = re.compile('^help(.*?)$')

# ---------------------------------------------------------------------------
# We cheat!
# This needs to be a Plugin so that it can register irc events easily, instead
# of putting a bunch of special-case code in the middle of PluginHandler or
# something like that. So this is a Plugin, but lives in classes and is always
# imported.
class Helper(Plugin):
	"""
	Provide help on using blamehangle's irc commands.

	Plugins execute a self.setHelp(topic, command, help_text) command.
	Users on IRC can then say "help" to get a list of all the help topics, or
	"help <topic>" to get a list of commands fort he given topic, or 
	"help <topic> <command>" to get the help_text provided for that command.
	"""
	
	def setup(self):
		# a dictionary that maps topic names -> list of (command name, text)
		self.__Help = {}
	
	def rehash(self):
		self.setup()
	
	def _message_PLUGIN_REGISTER(self, message):
		self.setTextEvent(HELPER_HELP, HELP_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# A plugin has just asked to register some help info
	def _message_SET_HELP(self, message):
		for topic, cmds in message.data.items():
			for command, help_text in cmds.items():
				self.__Help.setdefault(topic, {})[command] = help_text
	
	# A plugin wants to unregister some help info
	def _message_UNSET_HELP(self, message):
		for topic, cmds in message.data.items():
			# Skip topics that we don't even know about
			if not topic in self.__Help:
				continue
			
			# Delete any commands
			for command in cmds.keys():
				if command in self.__Help[topic]:
					del self.__Help[topic][command]
			
			# Delete the topic if it's empty now
			if self.__Help[topic] == {}:
				del self.__Help[topic]
	
	# -----------------------------------------------------------------------
	# Someone wants help on something
	def _trigger_HELPER_HELP(self, trigger):
		# Split it into nice parts
		parts = trigger.match.group(1).lower().strip().split()
		
		# If there are no extra parts, they want basic help
		if len(parts) == 0:
			replytext = 'Help topics: '
			topics = self.__Help.keys()
			topics.sort()
			replytext += ' \02;;\02 '.join(topics)
		
		# If there is one part, they want topic help
		elif len(parts) == 1:
			topic = parts[0]
			
			# Nasty hack for obligatory Monty Python reference
			if topic == 'help':
				replytext = "Help! Help! I'm being repressed!"
			
			elif topic in self.__Help:
				replytext = "Help commands in topic '\02%s\02': " % topic
				cmds = self.__Help[topic].keys()
				cmds.sort()
				replytext += ' \02;;\02 '.join(cmds)
			
			else:
				replytext = "No such help topic '%s'" % topic
		
		# If there are two parts, they want command help
		elif len(parts) == 2:
			topic, command = parts
			
			if topic in self.__Help:
				if command in self.__Help[topic]:
					replytext = self.__Help[topic][command]
				else:
					replytext = "No such help topic '%s %s'" % (topic, command)
			else:
				replytext = "No such help topic '%s'" % topic
		
		# If there are more, someone is being stupid
		else:
			replytext = "Too many fields, try 'help'."
		
		# Spit it out
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
