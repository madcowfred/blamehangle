#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains the code that deals with all the plugins
# Blah, stuff
#----------------------------------------------------------------------------

import types, time

from classes.Plugin import *
from classes.Constants import *
from Plugins import *

from classes.Children import Child

#----------------------------------------------------------------------------

class PluginHandler(Child):
	"""
	This is the class that handles all the program <-> plugin communication.

	add detail here when there is detail to add.
	"""
	
	def setup(self):
		self.Plugins = self.pluginList()
		self.__PUBLIC_Events = {}
		self.__PUBLIC_D_Events = {}
		self.__MSG_Events = {}
		self.__NOTICE_Events = {}
		self.__CTCP_Events = {}
		self.__TIMED_Events = {}
	
	#------------------------------------------------------------------------
	
	# Upon startup, we send a message out to every plugin asking them for
	# the events they would like to trigger on.
	def run_once(self):
		for name in self.Plugins:
			self.sendMessage(name, PLUGIN_REGISTER, [])
	
	#------------------------------------------------------------------------

	# Check to see if we have any TIMED events that have expired their delai
	# time
	def run_sometimes(self, currtime):

		for name in self.__TIMED_Events:
			event, plugin = self.__TIMED_Events[name]
			if event.interval_elapsed(currtime):
				event.last_trigger = currtime
				self.sendMessage(plugin, PLUGIN_TRIGGER, event)
	
	#------------------------------------------------------------------------

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

	#------------------------------------------------------------------------

	# A plugin has responded
	def _message_PLUGIN_REGISTER(self, message):
		events = message.data
		
		for event in events:
			eventStore = self.__getRelevantStore(event.IRCType)

			if event.name in eventStore:
				errtext = "%s already has an event for %s" % (event.name, event.IRCType)
				raise ValueError, errtext
			else:
				eventStore[event.name] = (event, message.source)
	
	#------------------------------------------------------------------------
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
		
		normal = []
		exclusive = []
		
		for name in eventStore:
			event, plugin = eventStore[name]
			m = event.regexp.match(text)
			if m:
				trigger = PluginTextTrigger(event, m, conn, target, userinfo)
				if event.exclusive:
					exclusive.append([plugin, trigger])
				else:
					normal.append([plugin, trigger])
		
		if normal:
			for plugin, trigger in normal:
				self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
		
		elif exclusive:
			for plugin, trigger in exclusive:
				self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
	
	#------------------------------------------------------------------------		
	# We just got a reply from a plugin.
	def _message_PLUGIN_REPLY(self, message):
		reply = message.data

		if isinstance(reply.trigger, PluginTimedEvent):
			for name in reply.trigger.targets:
				self.sendMessage('ChatterGizmo', REQ_CONN, [name, (name, reply)])

		elif isinstance(reply.trigger, PluginTextTrigger):
			nick = reply.trigger.userinfo.nick
			target = reply.trigger.target
			conn = reply.trigger.conn
			if reply.trigger.event.IRCType == IRCT_PUBLIC \
				or reply.trigger.event.IRCType == IRCT_PUBLIC_D:
				
				if reply.process:
					tosend = "%s: %s" % (nick, reply.replytext)
				else:
					tosend = reply.replytext
				self.privmsg(conn, target, tosend)
			else:
				self.privmsg(conn, nick, reply.replytext)

		else:
			# wtf
			errtext = "Bad reply object: %s" % reply
			raise ValueError, errtext
				
	#------------------------------------------------------------------------		
	def _message_REPLY_CONN(self, message):
		conn, (name, reply) = message.data
		
		if conn:
			for target in reply.trigger.targets[name]:
				self.privmsg(conn, target, reply.replytext)
	
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

	#------------------------------------------------------------------------
