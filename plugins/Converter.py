# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
#
# Converts between different things

import re

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

CONVERT_CONVERT = 'CONVERT_CONVERT'
CONVERT_HELP = '\02convert\02 <amount> <type 1> \02to\02 <type 2> : Convert between different measurements?' 
CONVERT_RE = re.compile('^convert (?P<amt>[\d\.]+) (?P<from>\S+)(?: to | )(?P<to>\S+)$')

# ---------------------------------------------------------------------------

DISTANCE = {
	'miles': ('miles', 1609.34),
	'ft': ('feet', 0.3048),
	'in': ('inches', 0.0254),
	'km': ('kilometers', 1000),
	'm': ('meters', 1),
	'cm': ('centimeters', 0.01),
	'mm': ('millimeters', 0.001),
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
		
		if data['from'] == data['to']:
			replytext = "Don't be an idiot"
		
		elif data['from'] == 'c' and data['to'] == 'f':
			value = '%.1f' % ((data['amt'] * 9.0 / 5) + 32)
			replytext = '%s °C == %s °F' % (data['amt'], value)
		
		elif data['from'] == 'f' and data['to'] == 'c':
			value = '%.1f' % ((data['amt'] - 32) * 5.0 / 9)
			replytext = '%s °F == %s °C' % (data['amt'], value)
		
		else:
			if DISTANCE.has_key(data['from']):
				_from = DISTANCE[data['from']]
			else:
				found = [key for key,value in DISTANCE.items() if value[0] == data['from']]
				if found:
					_from = DISTANCE[found[0]]
				else:
					_from = None
			
			if DISTANCE.has_key(data['to']):
				_to = DISTANCE[data['to']]
			else:
				found = [key for key,value in DISTANCE.items() if value[0] == data['to']]
				if found:
					_to = DISTANCE[found[0]]
				else:
					_to = None
			
			if _from is None:
				replytext = '%(from)s is not a valid measurement' % data
			
			elif _to is None:
				replytext = '%(to)s is not a valid measurement' % data
			
			else:
				value = '%.2f' % (data['amt'] * _from[1] / _to[1])
				replytext = '%s %s == %s %s' % (data['amt'], _from[0], value, _to[0])
		
		self.sendReply(trigger, replytext)
