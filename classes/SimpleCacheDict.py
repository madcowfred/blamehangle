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
