# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Stores all sorts of information about IRC users."

# ---------------------------------------------------------------------------

# Shiny way to look at a channel.
class ChanInfo:
	def __init__(self, modelist):
		self.modes = {}
		self.users = {}
		
		# nick or address list
		for mode in modelist[0]:
			self.modes[mode] = []
		# always has a parameter
		for mode in modelist[1]:
			self.modes[mode] = None
		# only has a parameter when setting
		for mode in modelist[2]:
			self.modes[mode] = None
		# never has a parameter
		for mode in modelist[3]:
			self.modes[mode] = False

# Shiny way to look at a user.
class UserInfo:
	def __init__(self, hostmask):
		self.nick, rest = hostmask.split('!')
		self.ident, self.host = rest.split('@')
	
	def __str__(self):
		return '%s (%s@%s)' % (self.nick, self.ident, self.host)
	
	def __repr__(self):
		return '<UserInfo: %s>' % (self.hostmask())
	
	def hostmask(self):
		return '%s!%s@%s' % (self.nick, self.ident, self.host)

# ---------------------------------------------------------------------------

class IRCUserList:
	def __init__(self):
		self._c = {}
		self._u = {}
		self._modelist = ['', '', '', '']
	
	# -----------------------------------------------------------------------
	# Remove a userinfo object if the user is no longer on any channels
	def __cleanup_user(self, ui):
		still_here = False
		for chan, ci in self._c.items():
			if ui in ci.users:
				still_here = True
				break
		
		if not still_here:
			del self._u[ui.nick]
	
	# -----------------------------------------------------------------------
	
	def get_userinfo(self, hostmask):
		nick = hostmask.split('!')[0]
		if nick not in self._u:
			self._u[nick] = UserInfo(hostmask)
		ui = self._u.get(nick, None)
		assert ui is not None
		return ui
	
	# -----------------------------------------------------------------------
	
	def chan_add_mode(self, chan, mode, extra):
		if mode in self._modelist[0]:
			if extra not in self._c[chan].modes[mode]:
				self._c[chan].modes[mode].append(extra)
		elif mode in self._modelist[1]:
			self._c[chan].modes[mode] = extra
		elif mode in self._modelist[2]:
			self._c[chan].modes[mode] = extra
		elif mode in self._modelist[3]:
			self._c[chan].modes[mode] = True
	
	def chan_del_mode(self, chan, mode, extra):
		if mode in self._modelist[0]:
			try:
				self._c[chan].modes[mode].remove(extra)
			except ValueError:
				pass
		elif mode in self._modelist[1]:
			self._c[chan].modes[mode] = None
		elif mode in self._modelist[2]:
			self._c[chan].modes[mode] = None
		elif mode in self._modelist[3]:
			self._c[chan].modes[mode] = False
	
	# -----------------------------------------------------------------------
	
	def user_joined(self, chan, hostmask=None):
		# Us
		if hostmask is None:
			self._c[chan] = ChanInfo(self._modelist)
		# Someone else
		else:
			nick = hostmask.split('!')[0]
			if nick not in self._u:
				self._u[nick] = UserInfo(hostmask)
			self._c[chan].users[self._u[nick]] = []
	
	def user_parted(self, chan, nick=None):
		# Us
		if nick is None:
			uis = self._c[chan].users.keys()
			del self._c[chan]
			
			_clean = self.__cleanup_user
			for ui in uis:
				_clean(ui)
			
		# Someone else
		else:
			ui = self._u.get(nick, None)
			assert ui is not None and ui in self._c[chan].users
			
			del self._c[chan].users[ui]
			
			self.__cleanup_user(ui)
	
	def user_quit(self, hostmask=None, nick=None):
		if nick is None:
			nick = hostmask.split('!')[0]
		ui = self._u.get(nick, None)
		assert ui is not None
		
		for chan, ci in self._c.items():
			if ui in ci.users:
				del ci.users[ui]
		
		del self._u[nick]
	
	def user_nick(self, oldnick, newnick):
		ui = self._u.get(oldnick, None)
		assert ui is not None
		
		ui.nick = newnick
		self._u[newnick] = ui
		del self._u[oldnick]
	
	# -----------------------------------------------------------------------
	
	def user_add_mode(self, chan, nick, mode):
		ui = self._u.get(nick, None)
		assert ui is not None
		
		if mode not in self._c[chan].users[ui]:
			self._c[chan].users[ui].append(mode)
	
	def user_del_mode(self, chan, nick, mode):
		ui = self._u.get(nick, None)
		assert ui is not None
		
		if mode in self._c[chan].users[ui]:
			self._c[chan].users[ui].remove(mode)
	
	# -----------------------------------------------------------------------
	
	def user_in_chan(self, chan, hostmask):
		ui = self._u.get(nick, None)
		
		return ui in self._c[chan]
	
	def user_in_any_chan(self, nick):
		ui = self._u.get(nick, None)
		if ui is None:
			return False
		
		for chan, uis in self._c.items():
			if ui in uis:
				return True
		return False
	
	def user_in_same_chan(self, nick1, nick2):
		ui1 = self._u.get(nick1, None)
		ui2 = self._u.get(nick2, None)
		if None in (ui1, ui2):
			return False
		
		for uis in self._c.values():
			if ui1 in uis and ui2 in uis:
				return True
		return False
	
	def user_has_mode(self, chan, nick, mode):
		ui = self._u.get(nick, None)
		assert ui is not None
		
		return mode in self._c[chan].users[ui]

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	u = IRCUserList()
	u.user_joined('#test')
	u.user_joined('#test', 'testbot!moo@cow.com')
	u.user_joined('#test', 'lamer!zug@dofaj.org')
	
	print u.user_has_mode('#test', 'testbot', 'o')
	u.user_add_mode('#test', 'testbot', 'o')
	print u.user_has_mode('#test', 'testbot', 'o')
	u.user_del_mode('#test', 'testbot', 'o')
