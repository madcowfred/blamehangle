# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Give help on using blamehangle's irc commands

from classes.Plugin import *
from classes.Constants import *
import re

BASIC_HELP = "BASIC_HELP"

BASIC_HELP_RE = re.compile("^help$")

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
	
	# -----------------------------------------------------------------------
	
	# A plugin has just asked to register some help info
	def _message_SET_HELP(self, message):
		topic, command, help_text = message.data

		# check if this is a new topic
		if not topic in self.__help:
			# create an empty help topic
			self.__help[topic] = []
			# register a new trigger for "help <this topic>"
			top_name = "**%s**" % topic
			top_pattern = re.compile("^help +(?P<topic>%s)$" % topic)
			top_dir = PluginTextEvent(top_name, IRCT_PUBLIC_D, top_pattern)
			top_msg = PluginTextEvent(top_name, IRCT_MSG, top_pattern)
			self.register(top_dir, top_msg)

		# add the help text for this command to our help for this topic
		self.__help[topic].append((command, help_text))
		
		# register a new trigger for this command
		com_name = "__%s__%s__" % (topic, command)
		com_pattern = re.compile("^help +(?P<topic>%s) +(?P<command>%s)$" % (topic, command))
		com_dir = PluginTextEvent(com_name, IRCT_PUBLIC_D, com_pattern)
		com_msg = PluginTextEvent(com_name, IRCT_MSG, com_pattern)
		self.register(com_dir, com_msg)

	# -----------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data

		# Someone simply asked for "help"
		if trigger.name == BASIC_HELP:
			replytext = "Help topics: "
			replytext += " \02;;\02 ".join(self.__help.keys())
			self.sendReply(trigger, replytext)

		# Someone asked for help on a topic
		elif trigger.name.startswith("**") and trigger.name.endswith("**"):
			topic = trigger.name[2:-2]
			replytext = "Help commands in topic '\02%s\02': " % topic
			commands = [com for com, text in self.__help[topic]]
			replytext += " \02;;\02 ".join(commands)
			self.sendReply(trigger, replytext)

		# Someone asked for help on a command
		elif trigger.name.startswith("__") and trigger.name.endswith("__"):
			name = trigger.name.replace(" ", "!#!#!@@@!#!#!")
			topic, command = name.replace("_", " ").split()
			topic = topic.replace("!#!#!@@@!#!#!", " ")
			command = command.replace("!#!#!@@@!#!#!", " ")
			help_text = [text for com, text in self.__help[topic] if com == command][0]
			replytext = "Help for '\02%s\02': " % command
			replytext += help_text
			#self.sendReply(trigger, replytext)
			self.sendReply(trigger, help_text)

		# Something went wrong
		else:
			errtext = "Helper got an unknown trigger: %s" % trigger.name
			raise ValueError, errtext
	
# ---------------------------------------------------------------------------
