# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Implements a user list for IRC."

class Userlist:
	def __init__(self):
		self.__u = {}
	
	def channels(self):
		return self.__u.keys()
	
	def joined(self, chan, nick=None):
		if nick is None:
			self.__u[chan] = {}
		elif nick not in self.__u[chan]:
			self.__u[chan][nick] = []
	
	def parted(self, chan, nick=None):
		if nick is None:
			del self.__u[chan]
		elif nick in self.__u[chan]:
			del self.__u[chan][nick]
	
	def quit(self, nick):
		for chan in self.__u.keys():
			self.parted(chan, nick)
	
	def nick(self, oldnick, newnick):
		for chan, nicks in self.__u.items():
			if oldnick in nicks:
				nicks[newnick] = nicks[oldnick]
				del nicks[oldnick]
	
	# -----------------------------------------------------------------------
	
	def add_mode(self, chan, nick, mode):
		if mode not in self.__u[chan][nick]:
			self.__u[chan][nick].append(mode)
	
	def del_mode(self, chan, nick, mode):
		if mode in self.__u[chan][nick]:
			self.__u[chan][nick].remove(mode)
	
	def has_mode(self, chan, nick, mode):
		return mode in self.__u[chan][nick]
	
	# -----------------------------------------------------------------------
	
	def in_chan(self, chan, nick):
		return nick in self.__u[chan]
	
	def in_any_chan(self, nick):
		for nicks in self.__u.values():
			if nick in nicks:
				return True
		return False
	
	def in_same_chan(self, nick1, nick2):
		for nicks in self.__u.values():
			if nick1 in nicks and nick2 in nicks:
				return True
		return False

# ---------------------------------------------------------------------------
