# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# A simple calculator

from classes.Plugin import *
from classes.Constants import *

import re

CALC = "CALC"

CALC_RE = re.compile("^ *[ ()0-9e.+\-*/%^]+$")


class Calculator(Plugin):
	"""
	A calculator for simple expressions.
	Operations allowed are addition, subtraction, division, multiplication,
	modulo, and exponentiation.
	
	Won't divide by zero or lame things like that.
	"""

	def _message_PLUGIN_REGISTER(self, message):
		calc_dir = PluginTextEvent(CALC, IRCT_PUBLIC_D, CALC_RE)
		calc_msg = PluginTextEvent(CALC, IRCT_MSG, CALC_RE)

		self.register(calc_dir, calc_msg)
	
	# --------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data

		if trigger.name == CALC:
			self.__calc(trigger)
		else:
			tolog = "Calculator got an unknown trigger: %s" % trigger
			self.putlog(LOG_WARNING, tolog)
	
	# --------------------------------------------------------------------------

	# We have been given a string containing an expression... so lets go ahead
	# and work it out!
	def __calc(self, trigger):
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
					newstr += "%s" % float(piece)

		# Try to evaluate the expression!
		# if it evals, give back the result, otherwise report an error
		try:
			result = eval(newstr)
		except ZeroDivisionError:
			replytext = "can't divide by zero"
			self.sendReply(trigger, replytext)
		except OverflowError, err:
			code, msg = err
			self.sendReply(trigger, msg)
		except Exception:
			replytext = "not a valid mathematical expression"
			self.sendReply(trigger, replytext)
		else:
			replytext = "%s" % result
			if replytext.endswith(".0"):
				replytext = replytext[:-2]
			self.sendReply(trigger, replytext)
