#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

"""
This file contains the main Plugin class, which all plugins are derived from.
It tries to hide a lot of our internal message passing architecture from the
plugin developer, and generally make life easier.

It also contains the various Triggers and Events that Plugins rely on.
"""

import cPickle
import os
import time

from classes.Children import Child
from classes.Constants import *

#----------------------------------------------------------------------------

class Plugin(Child):
	def __init__(self, *args, **kwargs):
		Child.__init__(self, *args, **kwargs)
		
		self.__setup_time = time.time()
		
		self.__Events = []
	
	# Default REQ_REHASH handler. We don't want to rehash just after we started!
	def _message_REQ_REHASH(self, message):
		if hasattr(self, 'rehash'):
			interval = time.time() - self.__setup_time
			
			if interval > 2:
				#tolog = '%s rehashing' % self._name
				#self.putlog(LOG_DEBUG, tolog)
				
				self.rehash()
			
			else:
				tolog = 'Not rehashing %s, started %.1fs ago!' % (self._name, interval)
				self.putlog(LOG_DEBUG, tolog)
	
	# Default PLUGIN_REGISTER handler. We have to reset things here!
	def _message_PLUGIN_REGISTER(self, message):
		if hasattr(self, 'register'):
			self.__Events = []
			self.register()
			# If we have some events, send them in
			if self.__Events:
				self.sendMessage('PluginHandler', PLUGIN_REGISTER, self.__Events)
		
		else:
			raise NameError, 'need to define register() in %s' % self._name
	
	# Default trigger handler
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		method = self._Get_Method(trigger.name)
		if method is not None:
			try:
				method(trigger)
			except:
				replytext = '%s crashed in %s()!' % (self._name, trigger.name)
				self.sendReply(trigger, replytext)
				raise
		else:
			raise NameError, 'define %s.%s or override _message_PLUGIN_TRIGGER' % (self._name, trigger.name)
	
	# -----------------------------------------------------------------------
	# Extend the default shutdown handler a little, so we can unset help stuff
	#def _message_REQ_SHUTDOWN(self, message):
	#	Child._message_REQ_SHUTDOWN(self, message)
	
	# -----------------------------------------------------------------------
	
	def sendReply(self, trigger, replytext, process=1):
		reply = PluginReply(trigger, replytext, process)
		self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
	
	# -----------------------------------------------------------------------
	# New way of setting text events
	def addTextEvent(self, method, regexp, IRCTypes=(IRCT_PUBLIC_D, IRCT_MSG), help=None, priority=10):
		event = PluginTextEvent(method.__name__, IRCTypes, regexp, help, priority)
		self.__Events.append(event)
	
	# New way of setting timed events
	def addTimedEvent(self, method, interval, targets=None, *args):
		event = PluginTimedEvent(method.__name__, interval, targets, args)
		self.__Events.append(event)
	
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
	
	# -----------------------------------------------------------------------
	# Basic thing to load our options into something easier to use
	def SetupOptions(self, section, dict=None):
		options = {}
		
		for option in self.Config.options(section):
			# Be nice to numbers
			value = self.Config.get(section, option)
			if value.isdigit():
				options[option] = long(value)
			else:
				options[option] = value
		
		return options

# ---------------------------------------------------------------------------

class PluginTextEvent:
	"""
	This class encapsulates all the data regarding an event that triggers off
	text from IRC.
	
	name     : a unique name for this event
	IRCTypes : the IRCTypes that this event should trigger on
	regexp   : a compiled re object that will be used to match against lines
	help     : (topic, command, text) tuple with help for this command
	priority : a priority value for this event. Events with higher priorities
	           will be preferred over low priorities.
	"""
	
	def __init__(self, name, IRCTypes, regexp, help, priority):
		self.name = name
		self.IRCTypes = IRCTypes
		self.regexp = regexp
		self.help = help
		self.priority = priority
	
	def __str__(self):
		return "%s: %s" % (self.IRCTypes, self.name)
	
	def __repr__(self):
		return "<class PluginTextEvent: %s>" % (self.__str__())

class PluginTextTrigger:
	"""
	This class holds all the information regarding the triggering of a text
	event.
	
	event    : the event that caused this trigger
	match    : the match object that was returned by the event's regexp
	IRCType  : the IRCType FIXME
	conn     : the IRC connection this trigger came from
	target   : the target of the line that caused this trigger (eg, channel)
	userinfo : a userinfo object for the source of the event
	"""
	
	def __init__(self, event, match, IRCType, conn, target, userinfo):
		self.event = event
		self.match = match
		self.IRCType = IRCType
		self.conn = conn
		self.target = target
		self.userinfo = userinfo
		self.name = self.event.name
	
	def __str__(self):
		return "%s, %s: %s, %s" % (self.name, self.IRCType, self.userinfo.nick, self.target)
	
	def __repr__(self):
		return "<class PluginTextTrigger:" + self.__str__() + ">"

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
	"""
	def __init__(self, name, interval, targets, args):
		self.name = name
		self.interval = interval
		self.targets = targets
		self.IRCTypes = (IRCT_TIMED,)
		self.last_trigger = time.time()
		self.help = None
		self.args = args
	
	def __str__(self):
		return "%s: %s" % (IRCT_TIMED, self.name)
	
	def __repr__(self):
		return "<class PluginTimedEvent: %s>" % (self.name)

class PluginTimedTrigger:
	def __init__(self, name, interval, targets, args):
		self.name = name
		self.interval =interval
		self.targets = targets
		self.IRCType = IRCT_TIMED
		self.args = args
	
	def __str__(self):
		return '%s' % (self.name)
	
	def __repr__(self):
		return "<class PluginTimedTrigger: %s>" % self.__str__()

# ---------------------------------------------------------------------------
# Needed sometimes for URL stuff, yeck
class PluginFakeTrigger:
	def __init__(self, name):
		self.name = name
		self.event = PluginTextEvent(name, None, None, None, 0)

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
