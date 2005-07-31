# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

'Converts between various distance/volume/weight measurements.'

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
	_HelpSection = 'math'
	
	def register(self):
		self.addTextEvent(
			method = self.__Convert,
			regexp = r'^convert (?P<amt>-?[\d\.]+)(?: from | )(?P<from>\S+)(?: to | )(?P<to>\S+)$',
			help = ('convert', '\02convert\02 <amount> <type 1> \02to\02 <type 2> : Convert between different measurements?'),
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
			replytext = '%s \xb0C == %s \xb0F' % (data['amt'], value)
		
		elif data['from'] == 'f' and data['to'] == 'c':
			value = '%.1f' % ((data['amt'] - 32) * 5.0 / 9)
			replytext = '%s \xb0F == %s \xb0C' % (data['amt'], value)
		
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
