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

"""
Implements threaded DNS lookups and a cache.
"""

import re
import socket
import time

from Queue import Empty, Queue
from threading import Lock, Thread

from classes.Children import Child
from classes.Common import MinMax
from classes.Constants import *
from classes.SimpleCacheDict import SimpleCacheDict

# ---------------------------------------------------------------------------
# This doesn't actually check for a valid IP, just the basic structure.
IPV4_RE = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

# ---------------------------------------------------------------------------

class Resolver(Child):
	def setup(self):
		self.DNSCache = self.loadPickle('.resolver_cache')
		if self.DNSCache is None:
			self.DNSCache = SimpleCacheDict(1)
		self.Requests = Queue(0)
		self.__threads = []
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('DNS')
		# Update the cache expiry time and trigger an expire
		self.DNSCache.cachesecs = self.Options['cache_time'] * 60
		self.DNSCache.expire()
	
	def shutdown(self, message):
		self.__Stop_Threads()
		
		self.DNSCache.expire()
		self.savePickle('.resolver_cache', self.DNSCache)
	
	# -----------------------------------------------------------------------
	# Start our threads just after we are created so an error here lets us
	# shut down cleanly
	def run_once(self):
		self.__Start_Threads()
	
	# -----------------------------------------------------------------------
	# Start our threads!
	def __Start_Threads(self):
		parentlock = Lock()
		for i in range(MinMax(1, 10, self.Options['resolver_threads'])):
			t = ResolverThread(self, parentlock, self.Requests, self.Options['use_ipv6'])
			#t = Thread(target=ResolverThread, args=(self, i))
			#t.setDaemon(1)
			t.setName('DNS%d' % i)
			t.start()
			self.__threads.append(t)
		
		tolog = 'Started %d resolver thread(s)' % (len(self.__threads))
		self.putlog(LOG_ALWAYS, tolog)
	
	# Stop our threads!
	def __Stop_Threads(self):
		# Tell all of our threads to exit
		for t in self.__threads:
			self.Requests.put(None)
		
		# Wait until all threads have stopped
		for t in self.__threads:
			t.join()
		
		tolog = 'All resolver threads halted'
		self.putlog(LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Someone wants us to resolve something, woo
	def _message_REQ_DNS(self, message):
		trigger, method, host, args = message.data
		
		# If the requested host is cached, just send that back
		if host in self.DNSCache:
			data = [trigger, method, self.DNSCache[host], args]
			self.sendMessage(message.source, REPLY_DNS, data)
		# If not, go resolve it
		else:
			# Well, make sure it's not an IP first, as we don't do reverse
			# lookups (yet)
			if IPV4_RE.match(host):
				data = [trigger, method, [(4, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			elif ':' in host:
				data = [trigger, method, [(6, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			else:
				self.Requests.put(message)

# ---------------------------------------------------------------------------

class ResolverThread(Thread):
	def __init__(self, parent, ParentLock, Requests, use_ipv6):
		Thread.__init__(self)
		self.parent = parent
		self.ParentLock = ParentLock
		self.Requests = Requests
		self.use_ipv6 = use_ipv6
	
	def run(self):
		while True:
			message = self.Requests.get()
			# None = die
			if message is None:
				return
			
			trigger, method, host, args = message.data
			
			hosts = []
			# If we want to use IPv6 at all, have to use getaddrinfo().
			if self.use_ipv6:
				try:
					results = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
				except socket.gaierror:
					pass
				else:
					# parse the results a bit here
					for af, socktype, proto, canonname, sa in results:
						if af == socket.AF_INET:
							hosts.append((4, sa[0]))
						elif af == socket.AF_INET6:
							hosts.append((6, sa[0]))
			
			# Otherwise we can use gethostbyname_ex, which doesn't interact badly
			# with broken name servers.
			else:
				try:
					results = socket.gethostbyname_ex(host)
				except socket.gaierror:
					pass
				else:
					hosts = [(4, h) for h in results[2]]
			
			if hosts == []:
				hosts = None
			data = [trigger, method, hosts, args]
			
			# Maybe cache the results and return them
			self.ParentLock.acquire()
			
			if hosts != []:
				self.parent.DNSCache[host] = hosts
			self.parent.sendMessage(message.source, REPLY_DNS, data)
			
			self.ParentLock.release()
			
			# Clean up temporary crap
			#del message, trigger, method, host, args, hosts, 

# ---------------------------------------------------------------------------
