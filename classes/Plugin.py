#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This contains the superclass for all plugins
#
# I'll make this more descriptive when there is actually something to
# describe
#----------------------------------------------------------------------------

import time

from classes.Children import Child
from classes.Constants import *

#----------------------------------------------------------------------------

class Plugin(Child):
	def __init__(self, *args, **kwargs):
		Child.__init__(self, *args, **kwargs)
		
		self.__Help = {}
	
	def _message_PLUGIN_REGISTER(self, message):
		raise Exception, 'need to overwrite PLUGIN_REGISTER message handler in %s' % self.__name
	
	def _message_PLUGIN_TRIGGER(self, message):
		raise Exception, 'need to overwrite PLUGIN_TRIGGER message handler in %s' % self.__name
	
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
	
	# -----------------------------------------------------------------------
	
	def setHelp(self, topic, command, help_text):
		self.__Help.setdefault(topic, {})[command] = help_text
	
	def registerHelp(self):
		self.sendMessage('Helper', SET_HELP, self.__Help)
	
	def unregisterHelp(self):
		self.sendMessage('Helper', UNSET_HELP, self.__Help)
	
	def register(self, *events):
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, events)

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
		nick = self.userinfo.nick
		IRCType = self.event.IRCType
		target = self.target
		return "%s, %s: %s, %s" % (name, IRCType, nick, target)
	
	def __repr__(self):
		return "<class PluginTextTrigger:" + self.__str__() + ">"

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
