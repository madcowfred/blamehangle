#!/usr/bin/env python

import irclib

# ---------------------------------------------------------------------------

class Blamehangle:
	"""
	The main class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def __init__(self):
		self.__ircobj = irclib.IRC()

# ---------------------------------------------------------------------------
