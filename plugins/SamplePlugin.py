#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file demonstrates the structure required by plugins.
# It doesn't actually -do- much, but is useful as a template.
#----------------------------------------------------------------------------

import re
from classes.Constants import *
from classes.Plugin import Plugin

class SamplePlugin(Plugin):
	"""
	A sample template for Blamehangle plugins
	"""

	
	#------------------------------------------------------------------------

	# A plugin can define the setup method if it has anything that needs to
	# happen while it is being created. This is called from the relevant
	# __init__() if it exists.
	def setup(self):
		# If you don't have anything you need to do during initialisation
		# for your plugin you can simply omit this method declaration entirely
		self.SAMPLE_TOKEN1 = "SAMPLE_TOKEN1"
		self.SAMPLE_TOKEN2 = "SAMPLE_TOKEN2"
		self.SAMPLE_TOKEN3 = "SAMPLE_TOKEN3"

		self.SAMPLE_RE1 = re.compile("abcdef$")
		self.SAMPLE_RE2 = re.compile("zzz (?P<some_name>.+)$")

		self.SAMPLE_TOKEN3_TARGETS = {
			'GoonNET': ['#grax','zharradan']
			}
	
	#------------------------------------------------------------------------

	# A plugin can define the run_once method if it has anything that needs
	# to happen after all plugins and other parts of the Blamehangle system
	# have been initialised, but before the main loop of the program has
	# been entered.
	def run_once(self):
		# If you don't need to do anything for run_once you can omit this
		# method entirely instead of just passing
		pass
	
	#------------------------------------------------------------------------

	# A plugin can define the run_always method if it has anything that needs
	# to be done during every iteration of the main control loop in
	# Blamehangle. This method will be called once per plugin per loop, if
	# defined.
	def run_always(self):
		# If you don't need to do anything in the main_loop you can omit this
		# method entirely instead of just passing
		pass
	
	#------------------------------------------------------------------------

	# Every plugin must define the _message_PLUGIN_REGISTER method, which
	# must behave by executing the statement
	#	self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	# where reply is a list of tuples describing the events you would like
	# to trigger for this plugin.
	#
	# The tuples must be of the form:
	#	(IRCtype, Criterion, PartsOfInterest, EventToken)
	# where:
	# 	* IRCtype is one of: PUBLIC, MSG, NOTICE, CTCP, TIMED
	# 	for messages to a channel, messages to the bot, notices to the bot,
	#	CTCPs to the bot, and time delayed recurring triggers respectively
	#
	#	* Criterion is a compiled regular expression object (from the re
	#	library) for all Types other than TIMED - for TIMED is is the delay in
	#	seconds desired between triggers.
	#
	#	* PartsOfInterest is a list of the groups from the regular expression
	#	you would like to have returned to you when a line is matched, for all
	#	Types other than TIMED. This list can contain group indexes, or names
	#	if your regular expression contains group naming. For TIMED events,
	#	this field is used to describe the targets you would like to send any
	#	reply to upon triggering this event, and is stored as a dictionary
	#	mapping a string (describing the network name) to a list of targets
	#
	#	* EventToken is a string that you would like to be sent upon the
	#	triggering of this event, so you can identify the cause of the trigger
	def _message_PLUGIN_REGISTER(self, message):
		# the message from PluginHandler -> our plugin does not contain any
		# data, so we don't need to worry about the contents of it here.
		#
		# XXX: this won't work until PluginHandler can turn strings into conns.
		# .. this will cause a blamehangle crash due to the timed event.
		reply = [
			(IRCT_MSG, self.SAMPLE_RE1, [0], self.SAMPLE_TOKEN1),
			(IRCT_PUBLIC, self.SAMPLE_RE2, ['some_name'], self.SAMPLE_TOKEN2),
			(IRCT_TIMED, 15, self.SAMPLE_TOKEN3_TARGETS, self.SAMPLE_TOKEN3)
			]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
	#------------------------------------------------------------------------

	# All plugins must implement the _message_PLUGIN_TRIGGER method, which
	# will be called whenever an event that this plugin has registered has
	# occured
	#
	# The message received will be of the following form:
	# [text, token, conn, IRCtype, target, userinfo] = message.data
	# where:
	#	* text will be a list of strings, those being the requested groups
	#	that matched from the regexp for all IRCtypes other than TIMED -
	#	for TIMED it will be a list of the targets we wish to reply to.
	#
	#	* token is the token used to identify this event (the one you set
	#	for each event in _message_PLUGIN_REGISTER)
	#
	#	* conn is an object describing which IRC connection this event
	#	came from. Ignored for TIMED (will be None)
	#
	#	* IRCtype is as described above
	#
	#	* target is the target of the IRC event that we matched against.
	#	Ignored for TIMED (will be None)
	#
	#	* userinfo is a userinfo object describing the instigator of the
	#	IRC event that we matched against. Ignored for TIMED (will be None)
	def _message_PLUGIN_TRIGGER(self, message):
		[text, token, conn, IRCtype, target, userinfo] = message.data

		# Check which event this trigger came from
		if token == self.SAMPLE_TOKEN1:
			self.__do_event1(conn, IRCtype, target, userinfo)
		elif token == self.SAMPLE_TOKEN2:
			self.__do_event2(text, conn, IRCtype, target, userinfo)
		elif token == self.SAMPLE_TOKEN3:
			self.__do_event3(text, token, IRCtype)
		else:
			# This should never happen, we received an event that we didn't
			# register!
			raise ValueError, "Unknown event: %s" % token
	
	#------------------------------------------------------------------------

	# If a plugin wants to send a reply back out to IRC, it must do so by
	# sending a PLUGIN_REPLY message to the PluginHandler, which must be
	# of the following form:
	# [replytext, conn, IRCtype, target, userinfo]
	# where:
	#	* replytext is the text that will be sent back to IRC.
	#	Note that the PluginHandler will handle things like adding a nick to
	#	the front of this text if it is a public message, this should just be
	#	the line you want to send back to IRC.
	#
	#	* conn, IRCtype, target, userinfo are the items retrieved from the
	#	PLUGIN_TRIGGER message, and must be returned unchanged.
	#
	# for example:
	# 	replytext = "Zugzug, heh heh."
	# 	reply = [replytext, conn, IRCtype, target, userinfo]
	# 	self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)

	#------------------------------------------------------------------------

	# Handle a SAMPLE_TOKEN1 event
	def __do_event1(self, conn, IRCtype, target, userinfo):
		replytext = "So you think abcdef is a command, huh?"
		reply = [replytext, conn, IRCtype, target, userinfo]
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------

	# Handle a SAMPLE_TOKEN2 event
	def __do_event2(self, text, conn, IRCtype, target, userinfo):
		# We only asked for one group from the regexp match, so text will be
		# a singleton list
		[data] = text
		replytext = "If this were a more complex plugin, I'd have something to say about %s" % data
		reply = [replytext, conn, IRCtype, target, userinfo]
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	#------------------------------------------------------------------------

	# Handle a SAMPLE_TOKEN3 event, which is a time-delayd trigger
	def __do_event3(self, targets, token, IRCtype):
		replytext = "Wow, 15 seconds have passed"
		reply = [replytext, None, IRCtype, targets, None]
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)

#----------------------------------------------------------------------------
