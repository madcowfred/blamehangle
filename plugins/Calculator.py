# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
A calculator for simple expressions.
Operations allowed are addition, subtraction, division, multiplication,
modulo, and exponentiation.

Won't divide by zero or lame things like that.
"""

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

CALC = "CALC"
CALC_RE = re.compile(r'^ *[ ()0-9e.+\-*/%^]+$')

CALC_OP_RE = re.compile(r'(?P<op>[+\-/*%^()])')

# ---------------------------------------------------------------------------

class Calculator(Plugin):
	def register(self):
		self.setTextEvent(CALC, CALC_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
	
	# --------------------------------------------------------------------------
	# We have been given a string containing an expression... so lets go ahead
	# and work it out!
	def _trigger_CALC(self, trigger):
		# mangle the string we have been given slightly.. remove any nasty
		# attempts at **, and change every number into a float
		calcstr = trigger.match.group(0)
		calcstr = re.sub("\*+", "*", calcstr)
		calcstr = CALC_OP_RE.sub(" \g<op> ", calcstr)
		
		# Loop through the input string, converting all numbers to floats, and
		# any ^ characters to **, which is python's exponent operator.
		pieces = calcstr.split()
		newstr = ''
		
		for piece in pieces:
			if CALC_OP_RE.match(piece):
				if piece == "^":
					newstr += "**"
				else:
					newstr += piece
			elif piece.endswith("e"):
				newstr += piece
			else:
				if newstr.endswith("e+") or newstr.endswith("e-"):
					newstr += piece
				else:
					try:
						newstr += "%s" % float(piece)
					except ValueError:
						newstr += "0"
		
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
			if replytext.endswith(".0"):
				replytext = replytext[:-2]
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
