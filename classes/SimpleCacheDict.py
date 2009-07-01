# Copyright (c) 2003-2009, blamehangle team
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

"""Simple caching dictionary object, destroys keys after <foo> seconds."""

import time

class SimpleCacheDict:
	def __init__(self, cachesecs, expirecount=10):
		self.cachesecs = cachesecs
		self.expirecount = expirecount
		
		self.__count = 0
		self.__items = {}
	
	def __contains__(self, k):
		try:
			v = self.__getitem__(k)
		except KeyError:
			return False
		else:
			return True
	
	def __getitem__(self, k):
		if k in self.__items:
			if time.time() - self.__items[k][0] >= self.cachesecs:
				del self.__items[k]
				raise KeyError, k
			else:
				return self.__items[k][1]
		else:
			raise KeyError, k
	
	def __setitem__(self, k, v):
		self.__items[k] = (time.time(), v)
		
		if self.expirecount:
			self.__count += 1
			if self.__count >= self.expirecount:
				self.expire()
	
	def get(self, k, v=None):
		try:
			return self.__getitem__(k)
		except KeyError:
			return v
	
	def expire(self):
		self.__count = 0
		now = time.time()
		for k, v in self.__items.items():
			if now - v[0] >= self.cachesecs:
				del self.__items[k]
