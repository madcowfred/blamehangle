# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
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
Implements threaded DNS lookups. getaddrinfo() lets the rest of the Python
interpreter run in 2.3+, yay.
"""

import re
import socket
import time

from Queue import Empty, Queue
from threading import Thread

from classes.Children import Child
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
		self.Threads = []
		
		self.rehash()
	
	def rehash(self):
		self._use_ipv6 = self.Config.getboolean('DNS', 'use_ipv6')
		
		self.Options = self.OptionsDict('DNS')
		# Update the cache expiry time and trigger an expire
		self.DNSCache.cachesecs = self.Options['cache_time'] * 60
		self.DNSCache.expire()
	
	def shutdown(self, message):
		self.__Stop_Threads()
		
		self.DNSCache.expire()
		self.savePickle('.resolver_cache', self.DNSCache)
	
	# We start our threads here to allow useful early shutdown
	def run_once(self):
		self.__Start_Threads()
	
	# -----------------------------------------------------------------------
	# Start our threads!
	def __Start_Threads(self):
		for i in range(self.Options['resolver_threads']):
			t = Thread(target=ResolverThread, args=(self, i))
			t.setDaemon(1)
			t.setName('Resolver %d' % i)
			self.Threads.append([t, 0])
			t.start()
			
			tolog = 'Started DNS thread: %s' % t.getName()
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
		trigger, method, host, args = message.data
		
		# If the requested host is cached, just send that back
		if host in self.DNSCache:
			data = [trigger, method, self.DNSCache[host], args]
			self.sendMessage(message.source, REPLY_DNS, data)
		# If not, go resolve it
		else:
			# Well, make sure it's not an IP first
			if IPV4_RE.match(host):
				data = [trigger, method, [(4, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			elif ':' in host:
				data = [trigger, method, [(6, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			else:
				self.Requests.put(message)

# ---------------------------------------------------------------------------

def ResolverThread(parent, myindex):
	_sleep = time.sleep
	
	while 1:
		# see if we have to die now
		if parent.Threads[myindex][1]:
			return
		
		# see if there's something to look up
		try:
			message = parent.Requests.get_nowait()
		except Empty:
			_sleep(0.1)
			continue
		
		# well, off we go then
		trigger, method, host, args = message.data
		
		#tolog = 'Looking up %s...' % host
		#parent.putlog(LOG_DEBUG, tolog)
		
		hosts = []
		# If we want to use IPv6 at all, have to use getaddrinfo().
		if parent._use_ipv6:
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
				
				parent.DNSCache[host] = hosts
				data = [trigger, method, hosts, args]
		
		# Otherwise we can use gethostbyname_ex, which doesn't interact badly
		# with retarded name servers.
		else:
			try:
				results = socket.gethostbyname_ex(host)
			except socket.gaierror:
				data = [trigger, method, None, args]
			else:
				hosts = [(4, h) for h in results[2]]
				parent.DNSCache[host] = hosts
				data = [trigger, method, hosts, args]
		
		# And return the message
		parent.sendMessage(message.source, REPLY_DNS, data)

# ---------------------------------------------------------------------------
