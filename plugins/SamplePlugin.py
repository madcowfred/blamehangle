# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file demonstrates the structure required by plugins.
# It doesn't actually -do- much, but is useful as a template.
# ---------------------------------------------------------------------------

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

class SamplePlugin(Plugin):
	"""
	A sample template for Blamehangle plugins
	"""
	
	# A plugin can define the setup method if it has anything that needs to
	# happen while it is being created. This is called from the relevant
	# __init__() if it exists.
	def setup(self):
		# If you don't have anything you need to do during initialisation
		# for your plugin you can simply omit this method declaration entirely
		self.SAMPLE_NAME1 = "SAMPLE_NAME1"
		self.SAMPLE_NAME2 = "SAMPLE_NAME2"
		self.SAMPLE_NAME3 = "SAMPLE_NAME3"
		
		self.SAMPLE_RE1 = re.compile("abcdef$")
		self.SAMPLE_RE2 = re.compile("zzz (?P<stuff>.+)$")
		
		self.SAMPLE_NAME3_TARGETS = {
			'SuperMegaNet': ['#moo']
			}
		
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_once method if it has anything that needs
	# to happen after all plugins and other parts of the Blamehangle system
	# have been initialised, but before the main loop of the program has
	# been entered.
	def run_once(self):
		# If you don't need to do anything for run_once you can omit this
		# method entirely instead of just passing
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_always method if it has anything that needs
	# to be done during every iteration of the main control loop in
	# Blamehangle. This method will be called once per plugin per loop, if
	# defined.
	def run_always(self):
		# If you don't need to do anything in the main_loop you can omit this
		# method entirely instead of just passing
		pass
	
	# -----------------------------------------------------------------------
	
	# Every plugin must define the _message_PLUGIN_REGISTER method, which
	# must call self.register with all it's events as arguments.
	def _message_PLUGIN_REGISTER(self, message):
		# the message from PluginHandler -> our plugin does not contain any
		# data, so we don't need to worry about the contents of it here.
		
		event1 = PluginTextEvent(self.SAMPLE_NAME1, IRCT_MSG, self.SAMPLE_RE1)
		event2 = PluginTextEvent(self.SAMPLE_NAME2, IRCT_PUBLIC, self.SAMPLE_RE2)
		event3 = PluginTimedEvent(self.SAMPLE_NAME3, 180, self.SAMPLE_NAME3_TARGETS)
		
		self.register(event1, event2, event3)
	
	# -----------------------------------------------------------------------
	
	# All plugins must implement the _message_PLUGIN_TRIGGER method, which
	# will be called whenever an event that this plugin has registered has
	# occured
	#
	# the message received will be either a PluginTimedEvent for timed
	# triggers, or a PluginTextTrigger for text triggers.
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == self.SAMPLE_NAME1:
			self.__do_event1(trigger)
		elif trigger.name == self.SAMPLE_NAME2:
			self.__do_event2(trigger)
		elif trigger.name == self.SAMPLE_NAME3:
			self.__do_event3(trigger)
		else:
			# This should never happen
			errtext = "Unknown event: %s" % trigger.name
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	# If a plugin wants to send a reply back out to IRC, it must do so by
	# calling self.sendReply(trigger, replytext) where trigger is the
	# trigger you are replying to, and replytext is the string to send to
	# irc
	# -----------------------------------------------------------------------
	# Handle a SAMPLE_TOKEN1 event
	def __do_event1(self, trigger):
		replytext = "So you think I'll reply if you say 'abcdef', huh? oh, wait.."
		self.sendReply(trigger, replytext)
	
	# Handle a SAMPLE_TOKEN2 event
	def __do_event2(self, trigger):
		text = trigger.match.group('stuff')
		replytext = "If this were a more complex plugin, I'd have something to say about %s" % text
		self.sendReply(trigger, replytext)
	
	# Handle a SAMPLE_TOKEN3 event, which is a time-delayd trigger
	def __do_event3(self, event):
		replytext = "Wow, %d seconds have passed" % event.interval
		self.sendReply(event, replytext)

# ---------------------------------------------------------------------------
