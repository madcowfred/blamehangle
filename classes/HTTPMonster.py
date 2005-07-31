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
An asynchronous URL retriever. Plugins can send a URL request to HTTPMonster
and they will receive a response message at a later time.
"""

import asyncore
import gzip
import re
import socket
import sys
import time
import urllib
import urlparse

from cStringIO import StringIO

from classes.async_buffered import buffered_dispatcher
from classes.Children import Child
from classes.Constants import *

# ---------------------------------------------------------------------------

dodgy_html_check = re.compile("href='(?P<href>[^ >]+)").search

line_re = re.compile('(?:\r\n|\r|\n)')

# ---------------------------------------------------------------------------

class HTTPMonster(Child):
	def setup(self):
		self.active = 0
		self.urls = []
		
		self._requests = 0
		self._totalbytes = 0
		
		self.rehash()
	
	def rehash(self):
		options = self.OptionsDict('HTTP')
		
		self.max_conns = max(1, min(10, options.get('connections', 4)))
		self.redirect_limit = max(1, min(10, options.get('redirect_limit', 3)))
		self.connect_timeout = max(1, min(60, options.get('connect_timeout', 20)))
		self.user_agent = options['useragent']
		
		self.use_ipv6 = self.Config.getboolean('DNS', 'use_ipv6')
		self.dns_order = self.Config.get('DNS', 'http_order').strip().split()
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		# See if we should start a new HTTP transfer
		if self.urls and self.active < self.max_conns:
			host, message, chunks = self.urls.pop(0)
			
			# Nasty hack to allow redirects to work properly
			if hasattr(message, '_seen'):
				seen = message._seen
				del message._seen
			else:
				seen = {}
			
			async_http(self, host, message, chunks, seen)
		
		# See if anything has timed out
		for a in [a for a in asyncore.socket_map.values() if isinstance(a, async_http)]:
			a.timeout_check(currtime)
	
	# -----------------------------------------------------------------------
	# Someone wants us to go fetch a URL
	def _message_REQ_URL(self, message):
		self._requests += 1
		
		# We need to quote spaces
		url = re.sub(r' ', '%20', message.data[2])
		
		# Parse the URL into chunky bits
		chunks = urlparse.urlparse(url)
		
		# And go off to resolve the host
		host = chunks[1].split(":", 1)[0]
		self.dnsLookup(None, self.__DNS_Reply, host, message, chunks)
	
	# We got a DNS reply, deal with it. This is quite yucky.
	def __DNS_Reply(self, trigger, hosts, args):
		message, chunks = args
		
		# Do our IPv6 check here
		if hosts:
			if self.use_ipv6:
				if self.dns_order:
					new = []
					for f in self.dns_order:
						new += [h for h in hosts if h[0] == int(f)]
					hosts = new
			else:
				hosts = [h for h in hosts if h[0] == 4]
		
		# We got no hosts, DNS failure!
		if hosts is None or hosts == []:
			trigger, method, url = message.data[:3]
			
			# Log an error
			if hosts is None:
				tolog = "Error while trying to fetch URL '%s': DNS failure" % (url)
			else:
				tolog = "Error while trying to fetch URL '%s': no valid DNS results" % (url)
			self.putlog(LOG_ALWAYS, tolog)
			
			# Build the response and return it
			resp = HTTPResponse(url, None, None, None)
			data = [trigger, method, resp]
			self.sendMessage(message.source, REPLY_URL, data)
			
			return
		
		# Queue it up for snarfing later
		self.urls.append((hosts, message, chunks))
	
	# -----------------------------------------------------------------------
	# Someone wants some stats
	def _message_GATHER_STATS(self, message):
		message.data['http_reqs'] = self._requests
		message.data['http_bytes'] = self._totalbytes
		
		self.sendMessage('Postman', GATHER_STATS, message.data)

# ---------------------------------------------------------------------------

class async_http(buffered_dispatcher):
	def __init__(self, parent, hosts, message, chunks, seen):
		buffered_dispatcher.__init__(self)
		
		self._error = None
		self.closed = 0
		self.received = 0
		
		self.data = []
		self.headlines = []
		
		self.parent = parent
		self.hosts = hosts
		self.message = message
		self.chunks = chunks
		self.seen = seen
		
		self.trigger = message.data[0]
		self.method = message.data[1]
		# we need '+' instead of ' '
		self.url = re.sub(r'\s+', '%20', message.data[2])
		# POST parameters, but only if we're NOT redirecting!
		if message.data[3] and not seen:
			self.post_data = urllib.urlencode(message.data[3])
		else:
			self.post_data = None
		# Funky extra headers
		self.extra_headers = message.data[4] or None
		
		# Log what we're doing
		tolog = 'Fetching URL: %s' % (self.url)
		parent.putlog(LOG_DEBUG, tolog)
		
		# Parse the URL, saving the bits we need
		scheme, host, path, params, query, fragment = self.chunks
		
		# Work out our port from the host field
		try:
			host, port = host.split(":", 1)
			if port.isdigit():
				port = int(port)
			else:
				port = 80
		except (TypeError, ValueError):
			port = 80
		
		self.host = host
		self.port = port
		
		# Fix up the path field
		if not path:
			path = '/'
		if params:
			path = '%s;%s' % (path, params)
		if query:
			path = '%s?%s' % (path, query)
		
		self.path = path
		
		# Create the socket
		if self.hosts[0][0] == 4:
			self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		else:
			self.create_socket(socket.AF_INET6, socket.SOCK_STREAM)
		
		# Try to connect. It seems this will blow up if it can't resolve the
		# host.
		try:
			self.connect((self.hosts[0][1], port))
		except socket.error, msg:
			self.failed(msg)
		except socket.gaierror, msg:
			self.failed(msg)
		else:
			self.parent.active += 1
			self.last_activity = time.time()
	
	# Connection succeeded
	def handle_connect(self):
		self.last_activity = time.time()
		
		# POST is a bit more complimicated
		if self.post_data:
			text = 'POST %s HTTP/1.0\r\n' % (self.path)
			self.send(text)
			text = 'Content-type: application/x-www-form-urlencoded\r\n'
			self.send(text)
			text = 'Content-length: %d\r\n' % (len(self.post_data))
			self.send(text)
		# GET is simple
		else:
			text = 'GET %s HTTP/1.0\r\n' % (self.path)
			self.send(text)
		
		text = 'Host: %s\r\n' % (self.host)
		self.send(text)
		text = 'User-Agent: %s\r\n' % (self.parent.user_agent)
		self.send(text)
		text = 'Accept-Encoding: gzip\r\n'
		self.send(text)
		# Send any extra headers we have to
		if self.extra_headers:
			for k, v in self.extra_headers.items():
				text = '%s: %s\r\n' % (k, v)
				self.send(text)
		
		#text = "Connection: close\r\n"
		#self.send(text)
		self.send('\r\n')
		
		# Now we can send POST data
		if self.post_data:
			text = '%s\r\n' % (self.post_data)
			self.send(text)
	
	# Connection has data to read
	def handle_read(self):
		self.last_activity = time.time()
		
		try:
			chunk = self.recv(4096)
		except socket.error, msg:
			self.failed(msg)
		else:
			self.data.append(chunk)
			self.received += len(chunk)
	
	# Connection has been closed
	def handle_close(self):
		# Re-combine the data into one big chunk
		data = ''.join(self.data)
		
		# Try to split the data into header/body
		while 1:
			line, data = line_re.split(data, 1)
			
			if line:
				self.headlines.append(line)
			else:
				break
		
		# We have some data, might as well process it?
		if self.headlines:
			try:
				response = self.headlines[0].split()[1]
			except:
				failmsg = 'Invalid HTTP response: %s' % (repr(self.headlines[0]))
				self.failed(failmsg)
			else:
				# Build a header dictionary
				headers = {}
				for line in self.headlines[1:]:
					k, v = re.split(':+ ', line, 1)
					headers[k.lower()] = v
				
				# Various redirect responses
				if response in ('301', '302', '303', '307'):
					if 'location' in headers:
						newurl = urlparse.urljoin(self.url, headers['location'])
						
						if newurl in self.seen:
							self.failed('Redirection loop encountered!')
						else:
							self.seen[self.url] = 1
							if len(self.seen) > self.parent.redirect_limit:
								self.failed('Redirection limit reached!')
							else:
								self.message.data[2] = newurl
								self.message._seen = self.seen
								self.parent._message_REQ_URL(self.message)
					
					else:
						self.failed('Redirect without Location header!')
				
				# Not Modified
				elif response == '304':
					# Log something
					tolog = 'URL not modified: %s' % (self.url)
					self.parent.putlog(LOG_DEBUG, tolog)
					
					# Build the response and return it
					resp = HTTPResponse(self.url, response, headers, '')
					data = [self.trigger, self.method, resp]
					self.parent.sendMessage(self.message.source, REPLY_URL, data)
				
				# Anything else
				else:
					if len(data) > 0:
						page_text = None
						
						# Check for gzip
						is_gzip = 0
						
						if 'content-encoding' in headers:
							chunks = headers['content-encoding'].split()
							if 'gzip' in chunks:
								is_gzip = 1
							else:
								tolog = 'Unknown Content-Encoding: %s' % (repr(headers['content-encoding']))
								self.parent.pulog(LOG_WARNING, tolog)
						
						# If we think it's gzip compressed, try to unsquish it
						if is_gzip:
							try:
								gzf = gzip.GzipFile(fileobj=StringIO(data))
								page_text = gzf.read()
								gzf.close()
							except Exception, msg:
								self.failed('gunzip failed: %s' % msg)
						
						else:
							page_text = data[:]
						
						# And if we still have page text, keep going
						if page_text is not None:
							m = dodgy_html_check(page_text)
							while m:
								pre = page_text[:m.start()]
								post = page_text[m.end():]
								start, end = m.span('href')
								fixed = '"' + page_text[start:end - 1].replace("'", "%39") + '"'
								page_text = pre + 'href=' + fixed + post
								m = dodgy_html_check(page_text)
							
							# If it was compressed, log a bit extra
							if is_gzip:
								tolog = 'Finished fetching URL: %s - %d bytes (%d bytes)' % (self.url, len(data), len(page_text))
							else:
								tolog = 'Finished fetching URL: %s - %d bytes' % (self.url, len(page_text))
							self.parent.putlog(LOG_DEBUG, tolog)
							
							# Build the response and return it
							resp = HTTPResponse(self.url, response, headers, page_text)
							data = [self.trigger, self.method, resp]
							self.parent.sendMessage(self.message.source, REPLY_URL, data)
						
						# No text, log an error
						else:
							self.failed('no page text: response = %s' % response)
					
					# We got no data!
					else:
						self.failed('no data returned: response = %s' % response)
		
		# We got no header lines... strange
		else:
			self.failed('no headers returned')
		
		# Clean up
		if not self.closed:
			self.closed = 1
			self.parent.active -= 1
			self.parent._totalbytes += self.received
		
		self.close()
	
	# An exception occured somewhere
	def handle_error(self):
		_type, _value = sys.exc_info()[:2]
		
		if _type == 'KeyboardInterrupt':
			raise
		else:
			self.failed(_value)
	
	# See if we've timed out
	def timeout_check(self, currtime):
		if currtime - self.last_activity > self.parent.connect_timeout:
			self.failed('Connection timed out')
	
	# Failed!
	def failed(self, errormsg):
		tolog = "Error while trying to fetch URL '%s': %s" % (self.url, errormsg)
		self.parent.putlog(LOG_ALWAYS, tolog)
		
		# Build the response and return it
		resp = HTTPResponse(self.url, None, None, None)
		data = [self.trigger, self.method, resp]
		self.parent.sendMessage(self.message.source, REPLY_URL, data)
		
		# Clean up
		if not self.closed:
			self.closed = 1
			self.parent.active -= 1
			self.parent._totalbytes += self.received
		
		self.close()

# ---------------------------------------------------------------------------
# Simple class to wrap the data that we're returning
class HTTPResponse:
	def __init__(self, url, response, headers, data):
		self.url = url
		self.response = response
		self.headers = headers
		self.data = data

# ---------------------------------------------------------------------------
