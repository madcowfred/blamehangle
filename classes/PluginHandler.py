# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the code that deals with all the plugins

import time

from classes.Children import Child
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

LOG_QUERY  = "INSERT INTO commandlog (ctime, irctype, network, channel, user_nick, user_host, command)"
LOG_QUERY += " VALUES (%s, %s, %s, %s, %s, %s, %s)"

# ---------------------------------------------------------------------------

class PluginHandler(Child):
	"""
	This is the class that handles all the program <-> plugin communication.
	"""
	
	def setup(self):
		self._log_commands = self.Config.getboolean('logging', 'log_commands')
		
		self.Plugins = self.Config.get('plugin', 'plugins').split()
		self.Plugins.append('Helper')
		
		self.__Events = {}
		for IRCType in [IRCT_PUBLIC, IRCT_PUBLIC_D, IRCT_MSG, IRCT_NOTICE, IRCT_CTCP, IRCT_TIMED]:
			self.__Events[IRCType] = {}
	
	# -----------------------------------------------------------------------
	# Upon startup, we send a message out to every plugin asking them for
	# the events they would like to trigger on.
	def run_once(self):
		self.sendMessage(self.Plugins, PLUGIN_REGISTER, [])
	
	# -----------------------------------------------------------------------
	# Check to see if we have any TIMED events that need to trigger
	def run_sometimes(self, currtime):
		for event, plugin in self.__Events[IRCT_TIMED].values():
			if event.interval_elapsed(currtime):
				event.last_trigger = currtime
				trigger = PluginTimedTrigger(event)
				self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
	
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
			name = event.name
			if hasattr(event, 'args'):
				if len(event.args) > 0:
					name = '%s:%s' % (event.name, event.args)
			
			if name in self.__Events[event.IRCType]:
				errtext = "%s already has an event for %s" % (event.name, event.IRCType)
				raise ValueError, errtext
			else:
				self.__Events[event.IRCType][name] = (event, message.source)
	
	# A plugin wants to unregister an event (by name only for now)
	def _message_PLUGIN_UNREGISTER(self, message):
		IRCType, names = message.data
		
		for name in names:
			if name in self.__Events[IRCType]:
				del self.__Events[IRCType][name]
	
	# A plugin has died, unregister all of it's events
	def _message_PLUGIN_DIED(self, message):
		dead_name = message.data
		
		for IRCType, events in self.__Events.items():
			for event_name, (event, plugin_name) in events.items():
				if plugin_name == dead_name:
					del events[event_name]
		
		if dead_name in self.Plugins:
			self.Plugins.remove(dead_name)
	
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
		
		triggered = {}
		
		# Collect the events that have triggered
		for event, plugin in self.__Events[IRCtype].values():
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
			
			# Log the command if we have to
			if self._log_commands:
				if IRCtype == IRCT_PUBLIC: irct = 'public'
				elif IRCtype == IRCT_PUBLIC_D: irct= 'direct'
				elif IRCtype == IRCT_MSG: irct = 'privmsg'
				
				user_host = '%s@%s' % (userinfo.ident, userinfo.host)
				
				data = (time.time(), irct, conn.options['name'], target, userinfo.nick, user_host, text)
				self.dbQuery(None, None, LOG_QUERY, *data)
	
	# -----------------------------------------------------------------------
	# We just got a reply from the database.
	def _message_REPLY_QUERY(self, message):
		trigger, method, result = message.data
		
		# Error!
		if result is None:
			self.putlog(LOG_WARNING, "Database error occurred while inserting command log entry.")
	
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

# ---------------------------------------------------------------------------
