# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
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

class Converter(Plugin):
	_HelpSection = 'math'
	
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__Conversions = {}
		
		filename = os.path.join('data', 'conversions')
		try:
			conv_file = open(filename, 'r')
		except IOError:
			self.putlog(LOG_WARNING, "Can't find data/conversions!")
		else:
			section = None
			for line in conv_file:
				line = line.strip()
				# Skip empty/comments
				if not line or line.startswith('#'):
					continue
				
				# New section
				if line.startswith('-') and line.endswith('-'):
					section = line[1:-1]
					self.__Conversions[section] = {}
				# Entry!
				else:
					# (singular form) (plural form) (ratio to standard unit) [other names]
					parts = line.split()
					data = (float(parts[0]), parts[1].replace('_', ' '))
					for name in parts[1:]:
						self.__Conversions[section][name.replace('_', ' ')] = data
			
			conv_file.close()
	
	def register(self):
		self.addTextEvent(
			method = self.__Convert,
			regexp = r'^convert (?P<amt>-?[\d\.]+) (?P<from>.*?) to (?P<to>.*?)$',
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
		
		# Nasty temperature specific hack :(
		elif data['from'] in self.__Conversions['TEMPERATURE'] and data['to'] in self.__Conversions['TEMPERATURE']:
			fromtext = self.__Conversions['TEMPERATURE'][data['from']][1]
			totext = self.__Conversions['TEMPERATURE'][data['to']][1]
			
			value = data['amt']
			
			if totext == 'degrees fahrenheit':
				if fromtext == 'degrees kelvin':
					value -= 273.15
				value = (value * 9.0 / 5) + 32
			elif fromtext == 'degrees fahrenheit':
				value = (value - 32) * 5.0 / 9
				if totext == 'degrees kelvin':
					value += 273.15
			else:
				if fromtext == 'degrees celsius':
					value = value - 273.15
				else:
					value = value + 273.15
			
			replytext = '%s %s == %s %s' % (data['amt'], fromtext, value, totext)
		
		# The rest
		else:
			for MAP in self.__Conversions.values():
				_from = MAP.get(data['from'], None)
				_to = MAP.get(data['to'], None)
				
				if _from is not None and _to is not None:
					break
			
			if _from is None or _to is None:
				replytext = '%(from)s <-> %(to)s is not a valid conversion' % data
			else:
				value = '%.2f' % (data['amt'] * _from[0] / _to[0])
				replytext = '%s %s == %s %s' % (data['amt'], _from[1], value, _to[1])
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
