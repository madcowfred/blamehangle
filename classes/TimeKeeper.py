
__version__ = '$Id$'

# ---------------------------------------------------------------------------

#import errno
#import re
#import select
import time
#import types

from classes.Children import Child
from classes.Common import *
from classes.Constants import *


class TimedEvent:
	def __init__(self, source, ident, interval, args):
		self.source = source
		self.ident = ident
		self.interval = interval
		self.args = args
		
		self.started = time.time()
	
	def elapsed(self, currtime):
		if (currtime - self.started) >= self.interval:
			return 1
		else:
			return 0
	
	def data(self):
		return (self.ident, self.args)

# ---------------------------------------------------------------------------

class TimeKeeper(Child):
	"""
	This Child handles timed events. Sounds fun!
	"""
	
	def setup(self):
		self.__Events = {}
	
	def run_sometimes(self, currtime):
		for ident, event in self.__Events.items():
			if event.elapsed(currtime):
				self.sendMessage(event.source, REPLY_TIMER_TRIGGER, event.data())
				del self.__Events[ident]
	
	def _message_REQ_ADD_TIMER(self, message):
		ident, interval, args = message.data
		
		if ident in self.__Events:
			errortext = "'%s' tried to add duplicate timer '%s'" % (message.source, ident)
			raise ValueError, errortext
		
		else:
			self.__Events[ident] = TimedEvent(message.source, ident, interval, args)
	
	def _message_REQ_DEL_TIMER(self, message):
		ident = message.data
		
		if not ident in self.__Events:
			errortext = "'%s' tried to remove unknown timer '%s'" % (message.source, ident)
			raise ValueError, errortext
		
		else:
			del self.__Events[ident]
