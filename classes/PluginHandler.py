#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This file contains the code that deals with all the plugins
# Blah, stuff
#----------------------------------------------------------------------------

import types, time

from classes.Plugin import Plugin
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
		for token in self.__TIMED_Events:
			delay, last, targets, plugin = self.__TIMED_Events[token]
			# Is it time to trigger this TIMED event?
			if currtime - last >= delay:
				message = [targets, token, None, IRCT_TIMED, None, None]
				self.sendMessage(plugin, PLUGIN_TRIGGER, message)
				# Update the last trigger time
				self.__TIMED_Events[token] = (delay, currtime, targets, plugin)
	
	def run_always(self):
		pass
	
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

		for IRCtype, criterion, groups, token in events:
			eventStore = self.__getRelevantStore(IRCtype)
			
			# Make sure that there isn't already a registered event of this
			# name for this IRCtype
			if token in eventStore:
				raise ValueError, "%s already has a hook on %s" % token, IRCtype
			else:
				# Add this event to the events we know plugins are interested
				# in.
				
				# TIMED events need to be handled differently
				if IRCtype == IRCT_TIMED:
					eventStore[token] = (criterion, time.time(), groups, message.source)
				else:
					eventStore[token] = (criterion, groups, message.source)

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

		for event in eventStore:
			regexp, groups, plugin = eventStore[event]
			match = regexp.match(text)
			if match:
				# We found a winner!
				desired_text = []
				for group in groups:
					desired_text.append(match.group(group))
				message = [desired_text, event, conn, IRCtype, target, userinfo]
				self.sendMessage(plugin, PLUGIN_TRIGGER, message)
				
				# should a break or something go here?
				# do we want it to be possible to have more than one plugin
				# trigger on the same text?
		

	#------------------------------------------------------------------------		
	# We just got a reply from a plugin, containing the string it would like us
	# to send back out to IRC.
	def _message_PLUGIN_REPLY(self, message):
		text, conn, IRCtype, target, userinfo = message.data

		if IRCtype == IRCT_PUBLIC or IRCtype == IRCT_PUBLIC_D:
			# We are sending back to public, prepend the relevant nick
			tosend = "%s: %s" % (userinfo.nick, text)
			self.privmsg(conn, target, tosend)
		
		elif IRCtype == IRCT_TIMED:
			# We need to handle TIMED events differently, since they have a
			# dictionary describing the intended targets for the message on
			# each network
			for name in target:
				self.sendMessage('ChatterGizmo', REQ_CONN, [name, [name, target, text]])

		else:
			# all other types are responded to with a /msg
			self.privmsg(conn, userinfo.nick, text)
	
	#------------------------------------------------------------------------		
	def _message_REPLY_CONN(self, message):
		conn, [name, targets, text] = message.data
		
		if conn:
			for target in targets[name]:
				self.privmsg(conn, target, text)
	
	# -----------------------------------------------------------------------

	def __getRelevantStore(self, type):
		if type == IRCT_PUBLIC:
			return self.__PUBLIC_Events
		elif type == IRCT_PUBLIC_D:
			return self.__PUBLIC_D_Events
		elif type == IRCT_MSG:
			return self.__MSG_Events
		elif type == IRCT_NOTICE:
			return self.__NOTICE_Events
		elif type == IRCT_CTCP:
			return self.__CTCP_Events
		elif type == IRCT_TIMED:
			return self.__TIMED_Events
		else:
			# Some smartass has come up with a new event type
			raise AttributeError, "no such event type: %s" % type

	#------------------------------------------------------------------------

	# Need some magic that can turn a string of a network name into a
	# connection object for that network
	def __getConn(self, name):
		# Probably need to find a way to get the Postman to set an attribute
		# on PluginHandler that contains a list (or something) of all the
		# current connections, or a list of (name, conn) pairs.
		# or something.
		pass

