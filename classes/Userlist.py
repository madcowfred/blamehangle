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
		for chan in self.__u.keys():
			if oldnick in self.__u[chan]:
				self.__u[chan][newnick] = self.__u[chan][oldnick]
				del self.__u[chan][oldnick]
	
	def add_mode(self, chan, nick, mode):
		if add_mode not in self.__u[chan][nick]:
			self.__u[chan][nick].append(mode)
	
	def del_mode(self, chan, nick, mode):
		if add_mode in self.__u[chan][nick]:
			self.__u[chan][nick].remove(mode)
	
	def has_mode(self, chan, nick, mode):
		return mode in self.__u[chan][nick]
	
	def in_any_chan(self, nick):
		for nicks in self.__u.values():
			if nick in nicks:
				return 1
		return 0
