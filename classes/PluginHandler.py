#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains the code that deals with all the plugins
# Blah, stuff
#----------------------------------------------------------------------------

import types

from classes.Plugin import Plugin
from Plugins import *

#from classes.Something import Something_describing_irc_events
# maybe the above will just come from Constants

from classes.Children import Child

class PluginHandler(Child):
	"""
	This is the class that handles all the program <-> plugin communication.

	add detail here when there is detail to add.
	"""

	def setup(self):
		self.Plugins = self.pluginList()
		self.PUBLIC_Events = {}
		self.MSG_Events = {}
		self.NOTICE_Events = {}
		self.CTCP_Events = {}
		self.TIMED_Events = {}

#----------------------------------------------------------------------------

	# Upon startup, we send a message out to every plugin asking them for
	# the events they would like to trigger on.
	def run_once(self):
		for name in self.Plugins:
			self.sendMessage(name, PLUGIN_REGISTER, [])
	
#----------------------------------------------------------------------------

	# Generate a list of all the plugins.
	# This is a rather ugly hack, but I can't think of any better way to do
	# this.
	def pluginList(self):
		import Plugins
		plugin_list = []
		for name in dir(Plugins):
			obj = getattr(Plugins, name)
			if type(obj) == types.ClassType:
				if issubclass(obj, Plugin):
					plugin_list.append(name)
		return plugin_list

#----------------------------------------------------------------------------

	# A plugin has responded
	def _message_PLUGIN_REGISTER(self, message):
		events = message.data

		for type, criterion, groups, token in events:
			eventStore = self.__getRelevantStore(type)
			if token in eventStore:
				raise ValueError, "%s already has a hook on %s" % token, type
			else:
				# Add this event to our list of events we know plugins are
				# interested in. For all but events of the TIMED variety
				# the criterion will be a regexp to match against; for TIMED
				# it will be the desired delay (in seconds) between triggers.
				eventStore[token] = (criterion, groups, message.source)

#----------------------------------------------------------------------------

	# Something has happened on IRC, and we are being told about it. Search
	# through the appropriate collection of events and see if any match. If
	# we find a match, send the TRIGGER message to the appropriate plugin.
	#
	# Desired format of an IRC_EVENT:
	# [ type, author, target, text ]
	# where type is one of PUBLIC, MSG, NOTICE, CTCP
	# author is a userinfo for the guy that said whatever made this event
	# target is a channel name our our nick (or "me" or whatever)
	# and text is the text, obviously. ;)
	# I don't think ACTION should trigger a PUBLIC event.
	def _message_IRC_EVENT(self, message):
		type, userinfo, target, text = message.data

		eventStore = self.__getRelevantStore(type)
		for event in eventStore:
			regexp, groups, plugin = eventStore[event]
			match = regexp.match(text)
			if match:
				# We found a winner!
				desired_text = []
				for group in groups:
					desired_text.append(match.group(group))
				self.sendMessage(plugin, PLUGIN_TRIGGER, [desired_text, event])
				
				# should a break or something go here?
				# do we want it to be possible to have more than one plugin
				# trigger on the same text?
		
#----------------------------------------------------------------------------		
	def __getRelevantStore(self, type):
		if type == PUBLIC:
			return self.PUBLIC_Events
		elif type == MSG:
			return self.MSG_Events
		elif type == NOTICE:
			return self.NOTICE_Events
		elif type == CTCP:
			return self.CTCP_Events
		elif type == TIMED:
			return self.TIMED_Events
		else:
			# Some smartass has come up with a new event type
			raise AttributeError, "no such event type: %s" % type

