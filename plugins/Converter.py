# -*- coding: iso-8859-1 -*-
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
# Mapping of measurements to SI units (meters)
DISTANCE = {
	'miles': ('miles', 1609.34),
	'ft': ('feet', 0.3048),
	'in': ('inches', 0.0254),
	'km': ('kilometers', 1000),
	'm': ('meters', 1),
	'cm': ('centimeters', 0.01),
	'mm': ('millimeters', 0.001),
}

# Mapping of weights to, err, grams
WEIGHT = {
	'g': ('grams', 1),
	'kg': ('kilograms', 1000),
	'lb': ('pounds', 453.5923),
	'oz': ('ounces', 28.3495),
}

# ---------------------------------------------------------------------------

class Converter(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		convert_dir = PluginTextEvent(CONVERT_CONVERT, IRCT_PUBLIC_D, CONVERT_RE)
		convert_msg = PluginTextEvent(CONVERT_CONVERT, IRCT_MSG, CONVERT_RE)
		self.register(convert_dir, convert_msg)
		
		self.setHelp('convert', 'convert', CONVERT_HELP)
		
		self.registerHelp()
	
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
		
		if data['from'] == data['to']:
			replytext = "Don't be an idiot"
		
		elif data['from'] == 'c' and data['to'] == 'f':
			value = '%.1f' % ((data['amt'] * 9.0 / 5) + 32)
			replytext = '%s °C == %s °F' % (data['amt'], value)
		
		elif data['from'] == 'f' and data['to'] == 'c':
			value = '%.1f' % ((data['amt'] - 32) * 5.0 / 9)
			replytext = '%s °F == %s °C' % (data['amt'], value)
		
		else:
			for MAP in (DISTANCE, WEIGHT):
				_from = None
				_to = None
				
				if MAP.has_key(data['from']):
					_from = MAP[data['from']]
				else:
					for key, value in MAP.items():
						if value[0] == data['from']:
							_from = MAP[found[0]]
							break
						# Handle non-plurals too
						elif value[0].endswith('s') and value[0][:-1] == data['from']:
							_from = MAP[found[0]]
							break
				
				if MAP.has_key(data['to']):
					_to = MAP[data['to']]
				else:
					for key, value in MAP.items():
						if value[0] == data['from']:
							_to = MAP[found[0]]
							break
						# Handle non-plurals too
						elif value[0].endswith('s') and value[0][:-1] == data['from']:
							_to = MAP[found[0]]
							break
				
				if _from is not None and _to is not None:
					break
			
			if _from is None or _to is None:
				replytext = '%(from)s <-> %(to)s is not a valid conversion' % data
			else:
				value = '%.2f' % (data['amt'] * _from[1] / _to[1])
				replytext = '%s %s == %s %s' % (data['amt'], _from[0], value, _to[0])
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
