# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file implements the url retriever for blamehangle. Plugins can send
# a message to the class defined here asking for the contents of a page
# defined by the given url, and a new dispatcher will be spawned eventually
# to fetch the URL.
#
# This is done so that url requests will not cause the bot to hang if the
# remote http server responds slowly.

import asyncore
import gzip
import re
import socket
import sys
import time
import urllib
import urlparse

from cStringIO import StringIO

from classes.Children import Child
from classes.Constants import *
from classes.Common import *

# ---------------------------------------------------------------------------

dodgy_html_check = re.compile("href='(?P<href>[^ >]+)").search

line_re = re.compile('(?:\r\n|\r|\n)')

HTTP_TIMEOUT = 20
REDIRECT_LIMIT = 3

# ---------------------------------------------------------------------------

class HTTPMonster(Child):
	"""
	This class takes requests for URLs and fetches them asynchronously to
	ensure that the bot will not freeze due to slow servers, or whatever.
	"""
	
	def setup(self):
		self.active = 0
		self.urls = []
		
		self.rehash()
	
	def rehash(self):
		# Set up our connection limit
		if self.Config.has_option('HTTP', 'connections'):
			self.max_conns = min(1, max(10, self.Config.getint('HTTP', 'connections')))
		else:
			self.max_conns = 1
		
		# Set up our user-agent
		if self.Config.has_option('HTTP', 'useragent'):
			self.user_agent = self.Config.get('HTTP', 'useragent')
		else:
			self.user_agent = "Mozilla/5.0 (Windows; U; Windows NT 5.0; en-US; rv:1.5) Gecko/20031015 Firebird/0.7"
	
	# -----------------------------------------------------------------------
	
	def run_always(self):
		asyncore.poll()
		
		if self.urls and self.active < self.max_conns:
			host, message, chunks = self.urls.pop(0)
			async_http(self, host, message, chunks, {})
	
	def run_sometimes(self, currtime):
		for a in [a for a in asyncore.socket_map.values() if isinstance(a, async_http)]:
			a.timeout_check(currtime)
	
	# -----------------------------------------------------------------------
	
	def _message_REQ_URL(self, message):
		# We need to quote spaces
		url = re.sub(r'\s+', '%20', message.data[2])
		
		# Parse the URL into chunky bits
		chunks = urlparse.urlparse(url)
		
		# And go off to resolve the host
		host = chunks[1].split(":", 1)[0]
		self.dnsLookup(None, None, host, message, chunks)
	
	# We got a DNS reply, deal with it. This is quite yucky.
	def _message_REPLY_DNS(self, message):
		_, _, hosts, (origmsg, chunks) = message.data
		if hosts is None:
			# log an error here
			return
		
		# We want to prefer IPv4 connections
		hosts.sort()
		
		if self.active < self.max_conns:
			async_http(self, hosts[0][1], origmsg, chunks, {})
		else:
			self.urls.append((hosts[0][1], origmsg, chunks))

# ---------------------------------------------------------------------------

class async_http(asyncore.dispatcher_with_send):
	def __init__(self, parent, ip, message, chunks, seen):
		asyncore.dispatcher_with_send.__init__(self)
		
		self._error = None
		self.closed = 0
		
		self.data = []
		self.headlines = []
		
		self.parent = parent
		self.ip = ip
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
		
		# Log what we're doing
		tolog = 'Fetching URL: %s' % (self.url)
		parent.putlog(LOG_DEBUG, tolog)
		
		# Parse the URL, saving the bits we need
		scheme, host, path, params, query, fragment = urlparse.urlparse(message.data[2])
		
		# Work out our host/port from the host field
		try:
			host, port = host.split(":", 1)
			port = int(port)
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
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		
		# Try to connect. It seems this will blow up if it can't resolve the
		# host.
		try:
			self.connect((ip, port))
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
		
		self.data.append(self.recv(4096))
	
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
				self.data = data
				break
		
		# We have some data, might as well process it?
		if self.headlines:
			try:
				response = self.headlines[0].split()[1]
			except:
				failmsg = 'Invalid HTTP response: %s' % self.headlines[0]
				self.failed(failmsg)
			else:
				# Various redirect responses
				if response in ('301', '302', '303', '307'):
					for line in self.headlines[1:]:
						if line.startswith('Location:'):
							chunks = line.split(None, 1)
							if len(chunks) != 2:
								break
							newurl = chunks[1]
							if not newurl.startswith('http://'):
								newurl = 'http://%s:%s%s' % (self.host, self.port, newurl)
							
							if newurl in self.seen:
								self.failed('Redirection loop encountered!')
							else:
								self.seen[self.url] = 1
								if len(self.seen) > REDIRECT_LIMIT:
									self.failed('Redirection limit reached!')
								else:
									self.message.data[2] = newurl
									async_http(self.parent, self.ip, self.message, self.chunks, self.seen)
							
							break
				
				# Anything else
				else:
					if len(self.data) > 0:
						page_text = None
						
						# Check for gzip
						is_gzip = 0
						for line in self.headlines[1:]:
							if line.startswith('Content-Encoding:'):
								chunks = line.split()[1:]
								if 'gzip' in chunks:
									is_gzip = 1
									break
								else:
									tolog = 'Unknown Content-Encoding: %s' % ','.join(chunks)
									self.parent.pulog(LOG_WARNING, tolog)
						
						# If we think it's gzip compressed, try to unsquish it
						if is_gzip:
							try:
								gzf = gzip.GzipFile(fileobj=StringIO(self.data))
								page_text = gzf.read()
								gzf.close()
							except Exception, msg:
								self.failed('gunzip failed: %s' % msg)
						
						else:
							page_text = self.data[:]
						
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
								tolog = 'Finished fetching URL: %s - %d bytes (%d bytes)' % (self.url, len(self.data), len(page_text))
							else:
								tolog = 'Finished fetching URL: %s - %d bytes' % (self.url, len(page_text))
							self.parent.putlog(LOG_DEBUG, tolog)
							
							# Build the response and return it
							resp = HTTPResponse(self.url, response, self.headlines, page_text)
							data = [self.trigger, self.method, resp]
							self.parent.sendMessage(self.message.source, REPLY_URL, data)
						
						# No text, log an error
						else:
							self.failed('no page text: response = %s' % response)
		
		# Clean up
		if not self.closed:
			self.closed = 1
			self.parent.active -= 1
		
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
		if currtime - self.last_activity > HTTP_TIMEOUT:
			self.failed('Connection timed out')
	
	# Failed!
	def failed(self, errormsg):
		tolog = "Error while trying to fetch url: %s - %s" % (self.url, errormsg)
		self.parent.putlog(LOG_ALWAYS, tolog)
		
		# Build the response and return it
		resp = HTTPResponse(self.url, None, None, None)
		data = [self.trigger, self.method, resp]
		self.parent.sendMessage(self.message.source, REPLY_URL, data)
		
		# Clean up
		if not self.closed:
			self.closed = 1
			self.parent.active -= 1
		
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
