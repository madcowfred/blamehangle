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
import re
import socket
import sys
import time
import urllib
import urlparse

from classes.Children import Child
from classes.Constants import *
from classes.Common import *

# ---------------------------------------------------------------------------

dodgy_html_check = re.compile("href='(?P<href>[^ >]+)").search

HTTP_TIMEOUT = 5
REDIRECT_LIMIT = 3

# ---------------------------------------------------------------------------

class HTTPMonster(Child):
	"""
	The HTTPMonster
	This class takes requests for URLs and fetches them in a new thread
	to ensure that the bot will not freeze due to slow servers, or whatever
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
			async_http(self, self.urls.pop(0), {})
	
	def run_sometimes(self, currtime):
		for a in [a for a in asyncore.socket_map.values() if isinstance(a, async_http)]:
			a.timeout_check(currtime)
	
	# -----------------------------------------------------------------------
	
	def _message_REQ_URL(self, message):
		if self.active < self.max_conns:
			async_http(self, message, {})
		else:
			self.urls.append(message)

# ---------------------------------------------------------------------------

class async_http(asyncore.dispatcher_with_send):
	def __init__(self, parent, message, seen):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.closed = 0
		self.data = ''
		self._error = None
		self.header = ''
		
		self.parent = parent
		self.message = message
		self.seen = seen
		
		self.trigger = message.data[0]
		self.method = message.data[1]
		# we need '+' instead of ' '
		self.url = re.sub(r'\s+', '+', message.data[2])
		# POST parameters, but only if we're NOT redirecting!s
		if message.data[3] and not seen:
			self.post_data = urllib.urlencode(message.data[3])
		else:
			self.post_data = None
		
		# Log what we're doing
		tolog = 'Fetching URL: %s' % (self.url)
		parent.putlog(LOG_DEBUG, tolog)
		
		# Parse the URL, saving the bits we need
		scheme, host, path, params, query, fragment = urlparse.urlparse(self.url)
		
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
			self.connect((host, port))
		except socket.gaierror, msg:
			tolog = "Error while trying to fetch url: %s - %s" % (self.url, msg)
			self.parent.putlog(LOG_ALWAYS, tolog)
			self.close()
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
		
		self.data += self.recv(4096)
		
		if not self.header:
			chunks = self.data.split('\r\n\r\n', 1)
			if len(chunks) <= 1:
				# Some retarded web servers seem to send \n\n\n\n, try that instead
				chunks = self.data.split('\n\n\n\n', 1)
				if len(chunks) <= 1:
					return
			
			self.header = chunks[0]
			self.data = chunks[1]
			
			#print self.header.splitlines()
	
	# Connection has been closed
	def handle_close(self):
		# We have some data, might as well process it?
		if self.header:
			headlines = self.header.splitlines()
			try:
				response = headlines[0].split()[1]
			except:
				pass
			else:
				# Various redirect responses
				if response in ('301', '302', '303', '307'):
					for line in headlines[1:]:
						if line.startswith('Location:'):
							chunks = line.split(None, 1)
							if len(chunks) != 2:
								break
							newurl = chunks[1]
							if not newurl.startswith('http://'):
								newurl = 'http://%s:%s%s' % (self.host, self.port, newurl)
							
							if newurl in self.seen:
								tolog = 'Redirection loop encountered while trying to fetch %s' % (self.url)
								self.parent.putlog(LOG_WARNING, tolog)
							else:
								self.seen[self.url] = 1
								if len(self.seen) > REDIRECT_LIMIT:
									tolog = 'Redirection limit reached while trying to fetch %s' % (self.url)
									self.parent.putlog(LOG_WARNING, tolog)
								else:
									self.message.data[2] = newurl
									async_http(self.parent, self.message, self.seen)
							
							break
				
				# Anything else
				else:
					if len(self.data) > 0:
						page_text = self.data[:]
						m = dodgy_html_check(page_text)
						while m:
							pre = page_text[:m.start()]
							post = page_text[m.end():]
							start, end = m.span('href')
							fixed = '"' + page_text[start:end - 1].replace("'", "%39") + '"'
							page_text = pre + 'href=' + fixed + post
							m = dodgy_html_check(page_text)
						
						tolog = 'Finished fetching URL: %s - %d bytes' % (self.url, len(page_text))
						self.parent.putlog(LOG_DEBUG, tolog)
						
						data = [self.trigger, self.method, page_text]
						self.parent.sendMessage(self.message.source, REPLY_URL, data)
		
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
		print currtime, self.last_activity
		
		if currtime - self.last_activity > HTTP_TIMEOUT:
			self.failed('Connection timed out')
	
	# Failed!
	def failed(self, errormsg):
		tolog = "Error while trying to fetch url: %s - %s" % (self.url, errormsg)
		self.parent.putlog(LOG_ALWAYS, tolog)
		
		data = [self.trigger, self.method, None]
		self.parent.sendMessage(self.message.source, REPLY_URL, data)
		
		# Clean up
		if not self.closed:
			self.closed = 1
			self.parent.active -= 1
		
		self.close()

# ---------------------------------------------------------------------------
