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

import asyncore
import os
import re
import select
import sys

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
		
		self.Active_Requests = 0
		self.__Requests = []
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('DNS')
		# Update the cache expiry time and trigger an expire
		self.DNSCache.cachesecs = self.Options['cache_time'] * 60
		self.DNSCache.expire()
	
	def shutdown(self, message):
		#self.__Stop_Threads()
		
		self.DNSCache.expire()
		self.savePickle('.resolver_cache', self.DNSCache)
	
	def run_sometimes(self, currtime):
		while self.__Requests and self.Active_Requests < self.Options.get('active_resolvers', 2):
			message = self.__Requests.pop(0)
			NastyResolver(self, message)
	
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
			# Don't go resolving IPv4 addresses
			if IPV4_RE.match(host):
				data = [trigger, method, [(4, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			# Or IPv6 addresses
			elif ':' in host:
				data = [trigger, method, [(6, host)], args]
				self.sendMessage(message.source, REPLY_DNS, data)
			else:
				self.__Requests.append(message)

# ---------------------------------------------------------------------------

class NastyResolver:
	def __init__(self, parent, message):
		self.parent = parent
		self.message = message
		
		self.data = ''
		self.lines = []
		
		self.parent.Active_Requests += 1
		
		# Execute the command
		cmdline = '%s %s %s' % (sys.executable, 'utils/resolver.py', message.data[2])
		self._in = os.popen(cmdline, 'r')
		self._fileno = self._in.fileno()
		
		# Add ourselves to the poller
		asyncore.socket_map[self._fileno] = self
		asyncore.poller.register(self._fileno, select.POLLIN)
	
	def handle_error(self):
		raise
	
	def handle_read_event(self):
		self.data += self._in.read()
		
		lines = self.data.split('\0')
		self.lines.extend(lines[:-1])
		
		if lines[-1] == '__FAIL__':
			self.done()
		elif lines[-1] == '__END__':
			hosts = []
			for line in self.lines:
				t, h = line.split(None, 1)
				hosts.append((int(t), h))
			self.done(hosts)
		else:
			self.data = lines[-1]
	
	def done(self, hosts=None):
		trigger, method, host, args = self.message.data
		
		if hosts is not None:
			self.parent.DNSCache[host] = hosts
		
		data = [trigger, method, hosts, args]
		self.parent.sendMessage(self.message.source, REPLY_DNS, data)
		
		# Remove ourselves from the poller
		if self._fileno in asyncore.socket_map:
			del asyncore.socket_map[self._fileno]
		
		try:
			asyncore.poller.unregister(self._fileno)
		except KeyError:
			pass
		
		self._in.close()
		
		self.parent.Active_Requests -= 1

# ---------------------------------------------------------------------------
