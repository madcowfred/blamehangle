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
from classes.Plugin import *

# ---------------------------------------------------------------------------

CALC = "CALC"
CALC_RE = re.compile("^ *[ ()0-9e.+\-*/%^]+$")

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
		op_re = re.compile("(?P<op>[+\-/*%^()])")
		
		calcstr = re.sub("\*+", "*", calcstr)
		calcstr = op_re.sub(" \g<op> ", calcstr)
		
		pieces = calcstr.split()
		newstr = ""
		
		# Loop through the input string, converting all numbers to floats, and
		# any ^ characters to **, which is python's exponent operator.
		for piece in pieces:
			if op_re.match(piece):
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
		# if it evals, give back the result, otherwise report an error
		try:
			result = eval(newstr)
		except ZeroDivisionError:
			replytext = "can't divide by zero"
		except OverflowError, err:
			replytext = err[1]
		except ValueError, errtext:
			replytext = errtext
		except Exception:
			replytext = 'not a valid mathematical expression!'
		else:
			replytext = "%s" % result
			if replytext.endswith(".0"):
				replytext = replytext[:-2]
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
