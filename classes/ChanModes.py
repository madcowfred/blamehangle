# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Stores mode information about a channel."

class ChanModes:
	def __init__(self):
		self.modes = ['', '', '', '']
		self.__m = {}
	
	def joined(self, chan):
		self.__m[chan] = {}
		
		# nick or address list
		for mode in self.modes[0]:
			self.__m[chan][mode] = []
		# always has a parameter
		for mode in self.modes[1]:
			self.__m[chan][mode] = None
		# only has a parameter when setting
		for mode in self.modes[2]:
			self.__m[chan][mode] = None
		# never has a parameter
		for mode in self.modes[3]:
			self.__m[chan][mode] = False
	
	def add_mode(self, chan, mode, extra):
		if mode in self.modes[0]:
			if extra not in self.__m[chan][mode]:
				self.__m[chan][mode].append(extra)
		elif mode in self.modes[1]:
			self.__m[chan][mode] = extra
		elif mode in self.modes[2]:
			self.__m[chan][mode] = extra
		elif mode in self.modes[3]:
			self.__m[chan][mode] = True
	
	def del_mode(self, chan, mode, extra):
		if mode in self.modes[0]:
			try:
				self.__m[chan][mode].remove(extra)
			except ValueError:
				pass
		elif mode in self.modes[1]:
			self.__m[chan][mode] = None
		elif mode in self.modes[2]:
			self.__m[chan][mode] = None
		elif mode in self.modes[3]:
			self.__m[chan][mode] = False

# ---------------------------------------------------------------------------
