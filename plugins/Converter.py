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

MAPPINGS = {
	'c': ('°C',
		('f', lambda x: (x * 9.0 / 5) + 32),
	),
	'f': ('°F',
		('c', lambda x: (x - 32) * 5.0 / 9),
	),
	'miles': ('miles',
		('ft', lambda x: x * 5280),
		('km', lambda x: x * 1.609),
	),
	'ft': ('feet',
		('miles', lambda x: x / 5280),
		('in', lambda x: x * 12),
	),
	'in': ('inches',
		('ft', lambda x: x / 12),
	),
	'km': ('kilometers',
		('miles', lambda x: x / 1.609),
		('m', lambda x: x * 1000),
	),
	'm': ('meters',
		('km', lambda x: x / 1000),
		('cm', lambda x: x * 100),
	),
	'cm': ('centimeters',
		('m', lambda x: x / 100),
		('mm', lambda x: x * 10),
	),
	'mm': ('millimeters',
		('cm', lambda x: x / 10),
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
			found = [m for m in MAPPINGS[data['from']][1:] if m[0] == data['to']]
			if found:
				value = '%.2f' % found[0][1](data['amt'])
				result = '%s %s' % (value, MAPPINGS[data['to']][0])
				replytext = '%s %s == %s' % (data['amt'], MAPPINGS[data['from']][0], result)
			
			else:
				chain = []
				ret = 0
				try:
					ret = self.__Convert_Recurse(chain, {}, data['from'], data['to'], None)
				except RuntimeError:
					replytext = 'Recursion limit reached while trying to find path from %(from)s to %(to)s' % data
				else:
					if ret:
						chain.reverse()
						
						amt = data['amt']
						for thing in chain:
							amt = thing[1](amt)
						
						value = '%.2f' % amt
						result = '%s %s' % (value, MAPPINGS[thing[0]][0])
						replytext = '%s %s == %s' % (data['amt'], MAPPINGS[data['from']][0], result)
					else:
						replytext = 'Unable to find path from %(from)s to %(to)s' % data
		
		self.sendReply(trigger, replytext)
	
	
	def __Convert_Recurse(self, chain, visited, start, findme, prev):
		for m in MAPPINGS[start][1:]:
			if visited.has_key(m[0]) or m[0] == prev:
				continue
			
			if m[0] == findme:
				chain.append(m)
				return 1
			
			else:
				ret = self.__Convert_Recurse(chain, visited, m[0], findme, start)
				if ret:
					chain.append(m)
					return 1
