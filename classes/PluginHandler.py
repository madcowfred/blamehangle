# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the code that deals with all the plugins

import time
import types

from classes.Children import Child
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

class PluginHandler(Child):
	"""
	This is the class that handles all the program <-> plugin communication.
	
	add detail here when there is detail to add.
	"""
	
	def setup(self):
		self.Plugins = self.Config.get('plugin', 'plugins').split()
		self.Plugins.append('Helper')
		self.__PUBLIC_Events = {}
		self.__PUBLIC_D_Events = {}
		self.__MSG_Events = {}
		self.__NOTICE_Events = {}
		self.__CTCP_Events = {}
		self.__TIMED_Events = {}
	
	# -----------------------------------------------------------------------
	# Upon startup, we send a message out to every plugin asking them for
	# the events they would like to trigger on.
	def run_once(self):
		self.sendMessage(self.Plugins, PLUGIN_REGISTER, [])
	
	# -----------------------------------------------------------------------
	# Check to see if we have any TIMED events that have expired their delai
	# time
	def run_sometimes(self, currtime):
		for name in self.__TIMED_Events:
			event, plugin = self.__TIMED_Events[name]
			if event.interval_elapsed(currtime):
				event.last_trigger = currtime
				self.sendMessage(plugin, PLUGIN_TRIGGER, event)
	
	# -----------------------------------------------------------------------
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
		
		# hack, because we cheat and make Helper a plugin that isn't a plugin
		plugin_list.append('Helper')
		return plugin_list
	
	# -----------------------------------------------------------------------
	# Postman has asked us to rehash our config.
	# For PluginHandler, this involves clearing out all our plugin triggers,
	# and sending out a PLUGIN_REGISTER message again.
	def _message_REQ_REHASH(self, message):
		self.setup()
		self.run_once()
	
	# -----------------------------------------------------------------------
	# A plugin has responded
	def _message_PLUGIN_REGISTER(self, message):
		events = message.data
		
		for event in events:
			eventStore = self.__getRelevantStore(event.IRCType)
			
			name = event.name
			if hasattr(event, 'args'):
				if len(event.args) > 0:
					name = '%s:%s' % (event.name, event.args)
			
			if name in eventStore:
				errtext = "%s already has an event for %s" % (event.name, event.IRCType)
				raise ValueError, errtext
			else:
				eventStore[name] = (event, message.source)
	
	# A plugin wants to unregister an event (by name only for now)
	def _message_PLUGIN_UNREGISTER(self, message):
		IRCType, names = message.data
		eventStore = self.__getRelevantStore(IRCType)
		
		for name in names:
			if name in eventStore:
				del eventStore[name]
	
	# A plugin has died, unregister all of it's events
	def _message_PLUGIN_DIED(self, message):
		dead_name = message.data
		
		for store in (self.__PUBLIC_Events, self.__PUBLIC_D_Events, self.__MSG_Events,
			self.__NOTICE_Events, self.__CTCP_Events, self.__TIMED_Events):
			
			for event_name, (event, plugin_name) in store.items():
				if plugin_name == dead_name:
					del store[event_name]
	
	# -----------------------------------------------------------------------
	# Something has happened on IRC, and we are being told about it. Search
	# through the appropriate collection of events and see if any match. If
	# we find a match, send the TRIGGER message to the appropriate plugin.
	#
	# This will never happen with IRCtype == TIMED, since there is no way that
	# ChatterGizmo can come up with a TIMED IRC_EVENT. This lets us avoid
	# special case code here.
	def _message_IRC_EVENT(self, message):
		conn, IRCtype, userinfo, target, text = message.data
		
		eventStore = self.__getRelevantStore(IRCtype)
		
		triggered = {}
		
		for name in eventStore:
			event, plugin = eventStore[name]
			m = event.regexp.match(text)
			if m:
				trigger = PluginTextTrigger(event, m, conn, target, userinfo)
				triggered.setdefault(event.priority, []).append([plugin, trigger])
		
		# Sort out the events, and only trigger the highest priority one(s)
		if triggered:
			priorities = triggered.keys()
			priorities.sort()
			for plugin, trigger in triggered[priorities[-1]]:
				self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
	
	# -----------------------------------------------------------------------
	# We just got a reply from a plugin.
	def _message_PLUGIN_REPLY(self, message):
		reply = message.data
		
		if isinstance(reply.trigger, PluginTimedEvent):
			self.privmsg(reply.trigger.targets, None, reply.replytext)
		
		elif isinstance(reply.trigger, PluginTextTrigger):
			nick = reply.trigger.userinfo.nick
			target = reply.trigger.target
			conn = reply.trigger.conn
			if reply.trigger.event.IRCType in (IRCT_PUBLIC, IRCT_PUBLIC_D):
				if reply.process:
					tosend = "%s: %s" % (nick, reply.replytext)
				else:
					tosend = reply.replytext
				self.privmsg(conn, target, tosend)
			else:
				self.privmsg(conn, nick, reply.replytext)
		
		elif isinstance(reply.trigger, PluginFakeTrigger):
			tolog = "PluginFakeTrigger: '%s'" % reply.replytext
			self.putlog(LOG_DEBUG, tolog)
		
		else:
			# wtf
			errtext = "Bad reply object: %s" % reply
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	
	def __getRelevantStore(self, IRCType):
		if IRCType == IRCT_PUBLIC:
			return self.__PUBLIC_Events
		elif IRCType == IRCT_PUBLIC_D:
			return self.__PUBLIC_D_Events
		elif IRCType == IRCT_MSG:
			return self.__MSG_Events
		elif IRCType == IRCT_NOTICE:
			return self.__NOTICE_Events
		elif IRCType == IRCT_CTCP:
			return self.__CTCP_Events
		elif IRCType == IRCT_TIMED:
			return self.__TIMED_Events
		else:
			# Some smartass has come up with a new IRCType
			raise AttributeError, "no such event IRCType: %s" % IRCType

# ---------------------------------------------------------------------------
