# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Converts between different things

import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

CONVERT_CONVERT = 'CONVERT_CONVERT'
CONVERT_HELP = '\02convert\02 <amount> <type 1> \02to\02 <type 2> : Convert between different measurements?' 
CONVERT_RE = re.compile('^convert (?P<amt>[\d\.]+) (?P<from>\S+)(?: to | )(?P<to>\S+)$')

# ---------------------------------------------------------------------------

MAPPINGS = {
	'c': ('°C',
		('f', lambda x: (x * 9.0 / 5) + 32)
	),
	'f': ('°F',
		('c', lambda x: (x - 32) * 5.0 / 9)
	),
	'miles': ('miles',
		('km', lambda x: x * 1.609),
		('m', lambda x: x * 1609)
	),
	'km': ('kilometers',
		('miles', lambda x: x * 0.621),
		('m', lambda x: x * 1000)
	),
	'm': ('meters',
		('km', lambda x: x / 1000),
		('miles', lambda x: x * 0.000621)
	)
}

# ---------------------------------------------------------------------------

class Converter(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		convert_dir = PluginTextEvent(CONVERT_CONVERT, IRCT_PUBLIC_D, CONVERT_RE)
		convert_msg = PluginTextEvent(CONVERT_CONVERT, IRCT_MSG, CONVERT_RE)
		self.register(convert_dir, convert_msg)
		
		self.setHelp('convert', 'convert', CONVERT_HELP)
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == CONVERT_CONVERT:
			self.__Convert(trigger)
	
	# -----------------------------------------------------------------------
	
	def __Convert(self, trigger):
		data = {}
		data['amt'] = float(trigger.match.group('amt'))
		data['from'] = trigger.match.group('from').lower()
		data['to'] = trigger.match.group('to').lower()
		
		if not MAPPINGS.has_key(data['from']):
			replytext = '%(from)s is not a valid measurement' % data
		
		elif not MAPPINGS.has_key(data['to']):
			replytext = '%(to)s is not a valid measurement' % data
		
		else:
			useme = [to for to in MAPPINGS[data['from']][1:] if to[0] == data['to']]
			if useme:
				value = '%.2f' % useme[0][1](data['amt'])
				result = '%s %s' % (value, MAPPINGS[data['to']][0])
				replytext = '%s %s == %s' % (data['amt'], MAPPINGS[data['from']][0], result)
			
			else:
				replytext = 'Unable to convert between %(from)s and %(to)s' % data
		
		self.sendReply(trigger, replytext)
