# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Converts between various distance/volume/weight measurements.'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------
# Mapping of distance measurements to SI units (meters)
DISTANCE = {
	'in': ('inches', 0.0254),
	'ft': ('feet', 0.3048),
	'yd': ('yards', 0.9144),
	'miles': ('miles', 1609.34),
	'mm': ('millimeters', 0.001),
	'cm': ('centimeters', 0.01),
	'm': ('meters', 1),
	'km': ('kilometers', 1000),
}

# Mapping of volume measurements to SI units (litres)
VOLUME = {
	'ml': ('millilitres', 0.001),
	'l': ('litres', 1),
	'pt': ('pints', 0.4731),
	'qt': ('quarts', 0.9463),
	'gal': ('gallons', 3.7854),
}

# Mapping of weight measurements to SI units (grams)
WEIGHT = {
	'mg': ('milligrams', 0.001),
	'cg': ('centigrams', 0.01),
	'g': ('grams', 1),
	'kg': ('kilograms', 1000),
	'oz': ('ounces', 28.3495),
	'lb': ('pounds', 453.5923),
	'stone': ('stone', 6350.2931),
	't': ('tonnes', 1000000),
}

# ---------------------------------------------------------------------------

class Converter(Plugin):
	def register(self):
		self.addTextEvent(
			method = self.__Convert,
			regexp = re.compile('^convert (?P<amt>-?[\d\.]+) (?P<from>\S+)(?: to | )(?P<to>\S+)$'),
			help = ('math', 'convert', '\02convert\02 <amount> <type 1> \02to\02 <type 2> : Convert between different measurements?'),
		)
	
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
			for MAP in (DISTANCE, VOLUME, WEIGHT):
				_from = None
				_to = None
				
				if MAP.has_key(data['from']):
					_from = MAP[data['from']]
				else:
					for key, value in MAP.items():
						if value[0] == data['from']:
							_from = value
							break
						# Handle non-plurals too
						elif value[0].endswith('s') and value[0][:-1] == data['from']:
							_from = value
							break
				
				if MAP.has_key(data['to']):
					_to = MAP[data['to']]
				else:
					for key, value in MAP.items():
						if value[0] == data['to']:
							_to = value
							break
						# Handle non-plurals too
						elif value[0].endswith('s') and value[0][:-1] == data['to']:
							_to = value
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
