# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Implements threaded DNS lookups. These don't seem to block in Python 2.3,
but do in 2.2... oh well. It's about time for people to upgrade anyway :)
"""

import socket
import time

from Queue import Empty, Queue
from threading import Thread

from classes.Children import Child
from classes.Constants import *

# ---------------------------------------------------------------------------

class Resolver(Child):
	def setup(self):
		self.Last_Cleanup = time.time()
		self.Requests = Queue(0)
		
		self.DNSCache = {}
		self.Threads = []
		
		# Get our options
		self.__cache_length = self.Config.getint('DNS', 'cache_time') * 60
		self.__resolver_threads = self.Config.getint('DNS', 'resolver_threads')
	
	# Make sure we stop our threads at shutdown time
	def shutdown(self, message):
		self.__Stop_Threads()
	
	# We start our threads here to allow useful early shutdown
	def run_once(self):
		self.__Start_Threads()
	
	# Clean up our cache occasionally
	def run_sometimes(self, currtime):
		interval = currtime - self.Last_Cleanup
		if interval >= 60:
			for k in [k for k,v in self.DNSCache.items() if currtime - v[0] >= self.__cache_length]:
				del self.DNSCache[k]
	
	# -----------------------------------------------------------------------
	# Start our threads!
	def __Start_Threads(self):
		for i in range(self.__resolver_threads):
			t = Thread(target=ResolverThread, args=(self, i))
			t.setName('Resolver %d' % i)
			t.start()
			self.Threads.append([t, 0])
			
			tolog = "Started DNS thread: %s" % t.getName()
			self.putlog(LOG_DEBUG, tolog)
	
	# Stop our threads!
	def __Stop_Threads(self):
		_sleep = time.sleep
		
		# set the flag telling each thread that we would like it to exit
		for tinfo in self.Threads:
			tinfo[1] = 1
		
		# wait until all threads have exited
		while [t for t,s in self.Threads if t.isAlive()]:
			_sleep(0.1)
		
		self.putlog(LOG_DEBUG, "All DNS threads halted")
	
	# -----------------------------------------------------------------------
	# Someone wants us to resolve something, woo
	def _message_REQ_DNS(self, message):
		# If the requested host is cached, just send that back
		if message.data[2] in self.DNSCache:
			data = list(message.data[:2])
			data.append(self.DNSCache[message.data[2]][1])
			data.append(message.data[3])
			self.sendMessage(message.source, REPLY_DNS, data)
		
		# If not, go resolve it
		else:
			self.Requests.put(message)

# ---------------------------------------------------------------------------

def ResolverThread(parent, myindex):
	while 1:
		# see if we have to die now
		if parent.Threads[myindex][1]:
			return
		
		# see if there's something to look up
		try:
			message = parent.Requests.get(True, 0.25)
		
		except Empty:
			continue
		
		# well, off we go then
		trigger, method, host, args = message.data
		
		#tolog = 'Looking up %s...' % host
		#parent.putlog(LOG_DEBUG, tolog)
		
		try:
			results = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
		except socket.gaierror:
			data = [trigger, method, None, args]
		else:
			# parse the results a bit here
			hosts = []
			for af, socktype, proto, canonname, sa in results:
				if af == socket.AF_INET:
					hosts.append((4, sa[0]))
				elif af == socket.AF_INET6:
					hosts.append((6, sa[0]))
			
			parent.DNSCache[host] = (time.time(), hosts)
			data = [trigger, method, hosts, args]
		
		parent.sendMessage(message.source, REPLY_DNS, data)
