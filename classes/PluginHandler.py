# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

import re
import time

from classes.Children import Child
from classes.Constants import *
from classes.Message import Message
from classes.Plugin import *

# ---------------------------------------------------------------------------

LOG_QUERY  = "INSERT INTO commandlog (ctime, irctype, network, channel, user_nick, user_host, command)"
LOG_QUERY += " VALUES (%s, %s, %s, %s, %s, %s, %s)"

# ---------------------------------------------------------------------------

class PluginHandler(Child):
	"""
	This handles all of the IRC <-> plugin event nastiness.
	"""
	
	def setup(self):
		self._log_commands = self.Config.getboolean('logging', 'log_commands')
		
		self.Plugins = self.Config.get('plugin', 'plugins').split()
		
		self.__Events = {}
		for IRCType in [IRCT_PUBLIC, IRCT_PUBLIC_D, IRCT_MSG, IRCT_NOTICE, IRCT_CTCP, IRCT_TIMED]:
			self.__Events[IRCType] = {}
		self.__Help = {}
		
		# We need to register our helper. This is a bit of a nasty hack, but
		# it's certainly better than a fake Helper plugin being special-cased
		# in various places :)
		event = PluginTextEvent('_HELPER_', (IRCT_PUBLIC_D, IRCT_MSG), re.compile('^help(.*?)$'), None, 10)
		self.__Events[IRCT_PUBLIC_D]['_HELPER_'] = (event, self)
		self.__Events[IRCT_MSG]['_HELPER_'] = (event, self)
	
	# -----------------------------------------------------------------------
	# Upon startup, we send a message out to every plugin asking them for
	# the events they would like to trigger on.
	def run_once(self):
		if self.Plugins:
			self.sendMessage(self.Plugins, PLUGIN_REGISTER, [])
		else:
			self.putlog(LOG_WARNING, 'No plugins are loaded!')
	
	# When we're shutting down, we don't want to trigger events any more
	def shutdown(self, message):
		for k in self.__Events.keys():
			self.__Events[k] = {}
	
	# -----------------------------------------------------------------------
	# Check to see if we have any TIMED events that need to trigger. If we
	# have some, make a new PluginTimedTrigger and send it out
	def run_sometimes(self, currtime):
		ready = [(e, p) for e, p in self.__Events[IRCT_TIMED].values() if currtime - e.last_trigger >= e.interval]
		for event, plugin in ready:
			event.last_trigger = currtime
			trigger = PluginTimedTrigger(event.name, event.interval, event.targets, event.args)
			self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
	
	# -----------------------------------------------------------------------
	# Postman has asked us to rehash our config. We reset our events and ask
	# plugins for them again.
	def _message_REQ_REHASH(self, message):
		self.setup()
		self.run_once()
	
	# -----------------------------------------------------------------------
	# A plugin has responded
	def _message_PLUGIN_REGISTER(self, message):
		for event in message.data:
			name = event.name
			if hasattr(event, 'args') and event.args:
				name = '%s:%s' % (event.name, event.args)
			
			# PluginTextEvents are a bit complicated
			#if issubclass(PluginTextEvent, event):
			for IRCType in event.IRCTypes:
				if name in self.__Events[IRCType]:
					# FIXME: error message sucks
					errtext = "%s already has a %s event in %s" % (message.source, event.name, IRCType)
					raise ValueError, errtext
				
				# Store the event nicely
				self.__Events[IRCType][name] = (event, message.source)
			
			# Store any help for it if we have to
			if event.help:
				topic, command, help_text = event.help
				self.__Help.setdefault(topic, {})[command] = help_text
	
	# A plugin wants to unregister an event (by name only for now)
	def _message_PLUGIN_UNREGISTER(self, message):
		IRCType, names = message.data
		
		for name in names:
			if name in self.__Events[IRCType]:
				del self.__Events[IRCType][name]
	
	# A plugin has died, unregister all of it's events
	def _message_PLUGIN_DIED(self, message):
		dead_name = message.data
		
		# Delete any events it registered
		for IRCType, events in self.__Events.items():
			for event_name, (event, plugin_name) in events.items():
				if plugin_name == dead_name:
					del events[event_name]
		
		# Then remove it from our plugin list
		if dead_name in self.Plugins:
			self.Plugins.remove(dead_name)
	
	# -----------------------------------------------------------------------
	# Something has happened on IRC, and we are being told about it. Search
	# through the appropriate collection of events and see if any match. If
	# we find a match, send the TRIGGER message to the appropriate plugin.
	#
	# This will never happen with IRCType == TIMED, since there is no way that
	# ChatterGizmo can come up with a TIMED IRC_EVENT. This lets us avoid
	# special case code here.
	def _message_IRC_EVENT(self, message):
		conn, IRCType, userinfo, target, text = message.data
		
		triggered = {}
		
		# Collect the events that have triggered
		for event, plugin in self.__Events[IRCType].values():
			m = event.regexp.match(text)
			if m:
				triggered.setdefault(event.priority, []).append([plugin, event, m])
		
		# Sort out the events, and only trigger the highest priority one(s)
		if triggered:
			priorities = triggered.keys()
			priorities.sort()
			
			for plugin, event, m in triggered[priorities[-1]]:
				trigger = PluginTextTrigger(event, m, IRCType, conn, target, userinfo)
				if plugin is self:
					self.__Helper(trigger)
				else:
					self.sendMessage(plugin, PLUGIN_TRIGGER, trigger)
			
			# Log the command if we have to
			if self._log_commands:
				if IRCType == IRCT_PUBLIC: irct = 'public'
				elif IRCType == IRCT_PUBLIC_D: irct = 'direct'
				elif IRCType == IRCT_MSG: irct = 'privmsg'
				
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
		if isinstance(message, Message):
			reply = message.data
		elif isinstance(message, PluginReply):
			reply = message
		else:
			# wtf
			errtext = "Bad PLUGIN_REPLY message: %r" % (reply)
			raise ValueError, errtext
		
		if isinstance(reply.trigger, PluginTimedTrigger):
			self.privmsg(reply.trigger.targets, None, reply.replytext)
		
		elif isinstance(reply.trigger, PluginTextTrigger):
			nick = reply.trigger.userinfo.nick
			target = reply.trigger.target
			conn = reply.trigger.conn
			if reply.trigger.IRCType in (IRCT_PUBLIC, IRCT_PUBLIC_D):
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
			errtext = "Bad reply object: %r" % (reply)
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------
	# Our helpful helper
	def __Helper(self, trigger):
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
		reply = PluginReply(trigger, replytext, 1)
		self._message_PLUGIN_REPLY(reply)

# ---------------------------------------------------------------------------
