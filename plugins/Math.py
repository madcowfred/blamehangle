# Copyright (c) 2003-2009, blamehangle team
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

"""
Various mathetmatical commands.
"""

import re

from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

CALC_OP_RE = re.compile(r'(?P<op>[+\-/*%^()])')
STAR_PLUS_RE = re.compile(r'\*+')

# Minimum and maximums for base number conversion (64 bit signed int)
MIN_64BIT = -9223372036854775808
MAX_64BIT = 9223372036854775807

# ---------------------------------------------------------------------------

class Math(Plugin):
	"""
	Provides various useful (possibly) math functions.
	"""
	
	_HelpSection = 'math'
	
	def register(self):
		self.addTextEvent(
			method = self.__Base,
			regexp = r'^base (?P<from>\d+) *(?P<to>|\d+) (?P<number>[0-9A-Fa-f]+)$',
			help = ('base', '\x02base\x02 <from> [to] <number> : Convert <number> from base <from> to base [to] (default is 10).'),
		)
		self.addTextEvent(
			method = self.__Calc,
			regexp = r'^[ ()0-9e.+\-*/%^]+$',
			help = ('calc', '<expr> : Calculate the result of <expr>.'),
		)
	
	# --------------------------------------------------------------------------
	# Someone wants to do a base conversion
	def __Base(self, trigger):
		# Make sure the bases are valid
		base_from = int(trigger.match.group('from'))
		try:
			base_to = int(trigger.match.group('to'))
		except ValueError:
			base_to = 10
		
		if base_from < 2 or base_from > 16 or base_to < 2 or base_to > 16:
			self.sendReply(trigger, 'bases must be between 2 and 16!')
			return
		if base_from == base_to:
			self.sendReply(trigger, 'why bother?')
			return
		
		# Make sure the number is valid
		numstr = trigger.match.group('number').upper()
		
		if len(numstr) > 64:
			self.sendReply(trigger, 'number is too long!')
			return
		
		# Try to convert the number to decimal
		try:
			number = long(numstr, base_from)
		except ValueError:
			replytext = "'%s' is not a valid base %s number!" % (numstr, base_from)
			self.sendReply(trigger, replytext)
			return
		
		# If it's outside our range, cry
		if number < MIN_64BIT or number > MAX_64BIT:
			replytext = '%s is not a 64-bit signed integer!' % (numstr)
		# If the number is 0, we're all done
		elif number == 0:
			replytext = '%s (base %s) == 0 (base %s)' % (numstr, base_from, base_to)
		# If we're converting to decimal, we're all done
		elif base_to == 10:
			replytext = '%s (base %s) == %s (base 10)' % (numstr, base_from, number)
		# Guess we have to do some work
		else:
			newstr = str(number)
			if newstr[0] == '-':
				newstr = newstr[1:]
				negative = 1
			else:
				negative = 0
			
			# Go for it
			DIGITS = '0123456789ABCDEF'
			chars = []
			
			while number > 0:
				number, digit = divmod(number, base_to)
				chars.insert(0, DIGITS[digit])
			
			# Build the reply
			if negative:
				replytext = '%s (base %s) == -%s (base %s)' % (numstr, base_from, ''.join(chars), base_to)
			else:
				replytext = '%s (base %s) == %s (base %s)' % (numstr, base_from, ''.join(chars), base_to)
		
		# Send the reply!
		self.sendReply(trigger, replytext)
	
	# --------------------------------------------------------------------------
	# We have been given a string containing an expression... so work it out!
	def __Calc(self, trigger):
		# mangle the string we have been given slightly.. remove any nasty
		# attempts at **, and change every number into a float
		calcstr = trigger.match.group(0)
		calcstr = STAR_PLUS_RE.sub('*', calcstr)
		calcstr = CALC_OP_RE.sub(' \g<op> ', calcstr)
		
		# Loop through the input string, converting all numbers to floats, and
		# any ^ characters to **, which is python's exponent operator.
		pieces = calcstr.split()
		newstr = ''
		
		for piece in pieces:
			if CALC_OP_RE.match(piece):
				if piece == '^':
					newstr += '**'
				else:
					newstr += piece
			elif piece.endswith('e'):
				newstr += piece
			else:
				if newstr.endswith('e+') or newstr.endswith('e-'):
					newstr += piece
				else:
					try:
						newstr += '%s' % float(piece)
					except ValueError:
						newstr += '0'
		
		# Try to evaluate the expression!
		try:
			result = eval(newstr)
		except ZeroDivisionError:
			replytext = "Can't divide by zero!"
		except OverflowError, err:
			replytext = err[1]
		except ValueError, errtext:
			replytext = errtext
		except Exception:
			replytext = 'Not a valid mathematical expression!'
		else:
			replytext = str(result)
			if replytext.endswith('.0'):
				replytext = replytext[:-2]
		
		self.sendReply(trigger, replytext)
	
# ---------------------------------------------------------------------------
