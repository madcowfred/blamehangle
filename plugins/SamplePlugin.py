# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
This file demonstrates the structure and basic useful bits for plugins.
Someone write a sentence that makes sense here.
"""

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

SAMPLE_NAME1 = 'SAMPLE_NAME1'
SAMPLE_RE1 = re.compile(r'^sample1$')

SAMPLE_NAME2 = 'SAMPLE_NAME2'
SAMPLE_RE2 = re.compile(r'^sample2 (.+)$')

SAMPLE_NAME3 = 'SAMPLE_NAME3'
SAMPLE_TARGETS = {
	'SuperMegaNet': ['#moo'],
}

# ---------------------------------------------------------------------------

class SamplePlugin(Plugin):
	"""
	A sample template for Blamehangle plugins
	"""
	
	# A plugin can define the setup method if it has anything that needs to
	# happen while it is being created. This is called from Plugin's __init__().
	def setup(self):
		# If you don't have anything you need to do during initialisation
		# for your plugin you can simply omit this method entirely
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_once method if it has anything that needs
	# to happen after all plugins and other parts of the Blamehangle system
	# have been initialised, but before the main loop of the program has
	# been entered.
	def run_once(self):
		# If you don't need to do anything for run_once you can omit this
		# method entirely
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_always method if it has anything that needs
	# to be done during every iteration of the main control loop. This method
	# will be called once per plugin per loop, if defined. Please try not to
	# use this :)
	def run_always(self):
		# If you don't need to do anything in the main_loop you can omit this
		# method entirely
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_sometimes method if it has anything that needs
	# to be done not that often (currently every 4th main loop iteration, or
	# 0.20s). This method will be called once per plugin per loop, if defined.
	# Please try not to use this :) You can more than likely just use a timed
	# event to accomplish what you need to.
	def run_always(self):
		# If you don't need to do anything in the main_loop you can omit this
		# method entirely
		pass
	
	# -----------------------------------------------------------------------
	# Every plugin must define the register method, which should look
	# something like this.
	def register(self):
		# This is a private message event only
		self.setTextEvent(SAMPLE_NAME1, SAMPLE_RE1, IRCT_MSG)
		# This is a public message and public directed message event
		self.setTextEvent(SAMPLE_NAME2, SAMPLE_RE2, IRCT_PUBLIC, IRCT_PUBLIC_D)
		# This is a timed event, triggering every 180 seconds
		self.setTimedEvent(SAMPLE_NAME3, 180, self.SAMPLE_TARGETS3)
		
		# And now we register the events
		self.registerEvents()
	
	# -----------------------------------------------------------------------
	# For each event, you need to implement a handler. If you don't need to
	# do any DB work or go fetch a URL, you might as well put all of the event
	# logic in here.
	#
	# 'trigger' is a plugin event trigger, either PluginTextTrigger or
	# PluginTimedTrigger.
	def _handle_SAMPLE_NAME1(self, trigger):
		# This sends a reply to the person that triggered it, via whichever
		# IRC type it came from.
		self.sendReply(trigger, "hi, I'm a sample trigger")
	
	
	
	
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
