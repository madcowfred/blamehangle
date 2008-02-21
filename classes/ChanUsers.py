# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
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

"Stores information about users on a channel."

class ChanUsers:
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
	
	def get_chans(self, nick):
		chans = []
		for chan, nicks in self.__u.items():
			if nick in nicks:
				chans.append(chan)
		return chans

# ---------------------------------------------------------------------------
