# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Give help on using blamehangle's irc commands

from classes.Plugin import *
from classes.Constants import *
import re

# ---------------------------------------------------------------------------

BASIC_HELP = "BASIC_HELP"
BASIC_HELP_RE = re.compile("^help$")

# ---------------------------------------------------------------------------
# We cheat!
# This needs to be a Plugin so that it can register irc events easily, instead
# of putting a bunch of special-case code in the middle of PluginHandler or
# something like that. So this is a Plugin, but lives in classes and is always
# imported.
class Helper(Plugin):
	"""
	Provide help on using blamehangle's irc commands.

	Plugins execute a self.setHelp(topic, command, help_text) command
	Users on IRC can then say "help" to get a list of all the help topics, or
	"help <topic>" to get a list of commands fort he given topic, or 
	"help <topic> <command>" to get the help_text provided for that command.
	"""

	def setup(self):
		# a dictionary that maps topic names -> list of (command name, text)
		self.__help = {}

	def _message_REQ_REHASH(self, message):
		self.setup()

	def _message_PLUGIN_REGISTER(self, message):
		help_dir = PluginTextEvent(BASIC_HELP, IRCT_PUBLIC_D, BASIC_HELP_RE)
		help_msg = PluginTextEvent(BASIC_HELP, IRCT_MSG, BASIC_HELP_RE)

		self.register(help_dir, help_msg)
		
		# Obligatory Monty Python joke
		repress_re = re.compile('^help help$')
		repress_dir = PluginTextEvent('**repressed**', IRCT_PUBLIC_D, repress_re)
		self.register(repress_dir)
	
	# -----------------------------------------------------------------------
	# A plugin has just asked to register some help info
	def _message_SET_HELP(self, message):
		for topic, cmds in message.data.items():
			for command, help_text in cmds.items():
				# check if this is a new topic
				if not topic in self.__help:
					# create an empty help topic
					self.__help[topic] = {}
					# register a new trigger for "help <this topic>"
					top_name = "**%s**" % topic
					top_pattern = re.compile("^help +(?P<topic>%s)$" % topic)
					top_dir = PluginTextEvent(top_name, IRCT_PUBLIC_D, top_pattern)
					top_msg = PluginTextEvent(top_name, IRCT_MSG, top_pattern)
					self.register(top_dir, top_msg)
				
				# add the help text for this command to our help for this topic
				self.__help[topic][command] = help_text
				
				# register a new trigger for this command
				com_name = "__%s__%s__" % (topic, command)
				com_pattern = re.compile("^help +(?P<topic>%s) +(?P<command>%s)$" % (topic, command))
				com_dir = PluginTextEvent(com_name, IRCT_PUBLIC_D, com_pattern)
				com_msg = PluginTextEvent(com_name, IRCT_MSG, com_pattern)
				self.register(com_dir, com_msg)
	
	# -----------------------------------------------------------------------
	# A plugin wants to unregister some help info
	def _message_UNSET_HELP(self, message):
		names = []
		for topic, cmds in message.data.items():
			if not topic in self.__help:
				continue
			
			for command in cmds.keys():
				if command in self.__help[topic]:
					del self.__help[topic][command]
					
					name = '__%s__%s__' % (topic, command)
					names.append(name)
			
			# Empty topic, delete it too
			if self.__help[topic] == {}:
				del self.__help[topic]
				
				name = '**%s**' % (topic)
				names.append(name)
		
		self.sendMessage('PluginHandler', PLUGIN_UNREGISTER, [IRCT_PUBLIC_D, names])
		self.sendMessage('PluginHandler', PLUGIN_UNREGISTER, [IRCT_MSG, names])
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone simply asked for "help"
		if trigger.name == BASIC_HELP:
			if self.__help:
				replytext = "Help topics: "
				topics = self.__help.keys()
				topics.sort()
				replytext += " \02;;\02 ".join(topics)
			else:
				replytext = 'No help topics available'
			self.sendReply(trigger, replytext)
		
		# Someone asked for help on a topic
		elif trigger.name.startswith("**") and trigger.name.endswith("**"):
			topic = trigger.name[2:-2]
			if topic == 'repressed':
				replytext = "Help! Help! I'm being repressed!"
			else:
				replytext = "Help commands in topic '\02%s\02': " % topic
				cmds = self.__help[topic].keys()
				cmds.sort()
				replytext += " \02;;\02 ".join(cmds)
			
			self.sendReply(trigger, replytext)
		
		# Someone asked for help on a command
		elif trigger.name.startswith("__") and trigger.name.endswith("__"):
			name = trigger.name.replace(" ", "!#!#!@@@!#!#!")
			topic, command = name.replace("_", " ").split()
			topic = topic.replace("!#!#!@@@!#!#!", " ")
			command = command.replace("!#!#!@@@!#!#!", " ")
			help_text = self.__help[topic][command]
			self.sendReply(trigger, help_text)
		
		# Something went wrong
		else:
			errtext = "Helper got an unknown trigger: %s" % trigger.name
			raise ValueError, errtext
