# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Implements a user list for IRC."

class Userlist:
	def __init__(self):
		self.__u = {}
	
	def channels(self):
		return self.__u.keys()
	
	def self_join(self, chan):
		self.__u[chan] = {}
	
	def self_part(self, chan):
		del self.__u[chan]
	
	def user_join(self, chan, nick):
		if nick not in self.__u[chan]:
			self.__u[chan][nick] = 1
	
	def user_part(self, chan, nick):
		if nick in self.__u[chan]:
			del self.__u[chan][nick]
	
	def user_quit(self, nick):
		for chan in self.__u.keys():
			self.user_part(chan, nick)
	
	def user_nick(self, oldnick, newnick):
		for chan in self.__u.keys():
			if oldnick in self.__u[chan]:
				del self.__u[chan][oldnick]
				self.__u[chan][newnick] = 1
	
	def in_any_chan(self, nick):
		for chan in self.__u.keys():
			if nick in self.__u[chan]:
				return 1
		
		return 0
