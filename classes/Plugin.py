#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This contains the superclass for all plugins
#
# I'll make this more descriptive when there is actually something to
# describe
#----------------------------------------------------------------------------

import cPickle
import os
import time

from classes.Children import Child
from classes.Constants import *

#----------------------------------------------------------------------------

class Plugin(Child):
	def __init__(self, *args, **kwargs):
		Child.__init__(self, *args, **kwargs)
		
		self.__Events = {}
		self.__Help = {}
	
	def _message_PLUGIN_REGISTER(self, message):
		raise Exception, 'need to overwrite PLUGIN_REGISTER message handler in %s' % self.__name
	
	# Default trigger handler, looks for _trigger_EVENT_NAME
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		method_name = '_trigger_%s' % trigger.name
		
		if hasattr(self, method_name):
			getattr(self, method_name)(trigger)
		else:
			raise Exception, 'either make %s or overwrite _message_PLUGIN_TRIGGER' % method_name
	
	# Default query reply handler, eek
	def _message_REPLY_QUERY(self, message):
		trigger, method, result = message.data
		if method is not None:
			method(trigger, result)
	
	# Default URL reply handler, eek
	def _message_REPLY_URL(self, message):
		trigger, method, page_text = message.data
		if method is not None:
			method(trigger, page_text)
	
	# -----------------------------------------------------------------------
	# Extend the default shutdown handler a little, so we can unset help stuff
	def _message_REQ_SHUTDOWN(self, message):
		Child._message_REQ_SHUTDOWN(self, message)
		
		# Only unset our help if we're being shut down without a reason. We
		# should only get a reason when the entire bot is shutting down.
		if message.data is None and self.__Help:
			self.unregisterHelp()
	
	# -----------------------------------------------------------------------
	
	def sendReply(self, trigger, replytext, process=1):
		reply = PluginReply(trigger, replytext, process)
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	def register(self, *events):
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, events)
	
	# -----------------------------------------------------------------------
	# Shorthand way of setting text events
	def setTextEvent(self, name, regexp, *IRCTypes):
		for IRCType in IRCTypes:
			event = PluginTextEvent(name, IRCType, regexp)
			ident = '__%s__%s__' % (name, IRCType)
			self.__Events[ident] = event
	
	# Shorthand way of setting text events with a different priority
	def setTextEventPriority(self, priority, name, regexp, *IRCTypes):
		for IRCType in IRCTypes:
			event = PluginTextEvent(name, IRCType, regexp, priority)
			ident = '__%s__%s__' % (name, IRCType)
			self.__Events[ident] = event
	
	# Shorthand way of setting timed events
	def setTimedEvent(self, name, interval, targets, *args):
		event = PluginTimedEvent(name, interval, targets, *args)
		ident = '__%s__%s__' % (name, interval)
		self.__Events[ident] = event
	
	# Quick way to register our events
	def registerEvents(self):
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, self.__Events.values())
	
	# -----------------------------------------------------------------------
	# Help stuff
	def setHelp(self, topic, command, help_text):
		self.__Help.setdefault(topic, {})[command] = help_text
	
	def registerHelp(self):
		self.sendMessage('Helper', SET_HELP, self.__Help)
	
	def unregisterHelp(self):
		self.sendMessage('Helper', UNSET_HELP, self.__Help)
	
	# -----------------------------------------------------------------------
	# Pickle stuff
	def savePickle(self, filename, obj):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, 'wb')
		except:
			# We couldn't open our file :(
			tolog = "Unable to open %s for writing" % filename
			self.putlog(LOG_WARNING, tolog)
		else:
			tolog = "Saving pickle to %s" % filename
			self.putlog(LOG_DEBUG, tolog)
			# the 1 turns on binary-mode pickling
			cPickle.dump(obj, f, 1)
			f.flush()
			f.close()
	
	def loadPickle(self, filename):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, 'rb')
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			return None
		
		# We have a pickle!
		tolog = "Loading pickle from %s" % filename
		self.putlog(LOG_DEBUG, tolog)
		
		try:
			obj = cPickle.load(f)
		except:
			# Failed to read the pickle file
			self.putlog(LOG_DEBUG, 'Pickle load failed!')
			return None
		else:
			return obj

# ---------------------------------------------------------------------------

class PluginTextEvent:
	"""
	This class encapsulates all the data regarding an event that triggers off
	text from IRC.
	name     : a unique name for this event
	IRCType  : the IRCType this event should trigger on
	regexp   : a compiled re object that will be used to match against lines of
	           the appropriate IRCType
	priority : a priority value for this event. Events with higher priorities
	           will be preferred over low priorities.
	"""
	
	def __init__(self, name, IRCType, regexp, priority=10):
		self.name = name
		self.IRCType = IRCType
		self.regexp = regexp
		self.priority = priority
	
	def __str__(self):
		return "%s: %s" % (self.IRCType, self.name)
	
	def __repr__(self):
		return "<class PluginTextEvent:" + self.__str__() + ">"

# ---------------------------------------------------------------------------

class PluginTimedEvent:
	"""
	This class describes an event that triggers based on a time delay.
	name     : a unique name for this event
	interval : the length of time (in seconds) between triggers
	targets  : A dictionary mapping an irc network name (from the bots main
		config file) to a list of targets on that network. If the IRC
		network you are sending to allows multiple targets per PRIVMSG,
		you can bundle them together in the same element in the target
		list.
		
		eg, targets = { 'EFnet' : ['#chan1,#chan2', '#chan3'] }
	
	The following attributes are also available
	IRCType            : This will always be IRCT_TIMED
	last_trigger       : the time this event last triggered
	interval_elapsed() : returns true if the interval for this event has
		elapsed
	"""
	def __init__(self, name, interval, targets, *args):
		self.name = name
		self.interval = interval
		self.targets = targets
		self.IRCType = IRCT_TIMED
		self.last_trigger = time.time()
		self.args = args
	
	def __str__(self):
		return "%s: %s" % (IRCT_TIMED, self.name)
	
	def __repr__(self):
		return "<class PluginTimedEvent:" + self.__str__() + ">"
	
	def interval_elapsed(self, currtime):
		return currtime - self.last_trigger >= self.interval

# ---------------------------------------------------------------------------

class PluginTextTrigger:
	"""
	This class holds all the information regarding the triggering of a text
	event.
	The following attributes are available:
		event    : the event that caused this trigger
		match    : the match object that was returned by the event's regexp
		conn     : the IRC connection this trigger came from
		target   : the target of the line that caused this trigger (eg, chan
			name)
		userinfo : a userinfo object describing the guy that sent the line
			that caused this match
	"""
	
	def __init__(self, event, match, conn, target, userinfo):
		self.event = event
		self.match = match
		self.conn = conn
		self.target = target
		self.userinfo = userinfo
		self.name = self.event.name
	
	def __str__(self):
		name = self.name
		try:
			nick = self.userinfo.nick
		except AttributeError:
			nick = 'None'
		try:
			IRCType = self.event.IRCType
		except AttributeError:
			IRCType = 'None'
		target = self.target
		return "%s, %s: %s, %s" % (name, IRCType, nick, target)
	
	def __repr__(self):
		return "<class PluginTextTrigger:" + self.__str__() + ">"

# ---------------------------------------------------------------------------
# Needed sometimes for URL stuff, yeck
class PluginFakeTrigger:
	def __init__(self, name):
		self.name = name
		self.event = PluginTextEvent(name, None, None)

# ---------------------------------------------------------------------------

class PluginReply:
	"""
	This class describes a reply generated by a plugin.
	trigger   : the trigger that this is a reply to
	replytext : the text of the reply to send back to irc
	process   : optional argument flagging whether PluginHandler should do
		any text processing on the replytext at all, or just send it verbatim

	"""
	def __init__(self, trigger, replytext, process=1):
		self.trigger = trigger
		self.replytext = replytext
		self.process = process
	
	def __str__(self):
		name = self.trigger.name
		text = self.replytext
		return "%s: %s" % (name, text)
	
	def __repr__(self):
		return "<class PluginReply: " + self.__str__() + ">"
