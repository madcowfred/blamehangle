# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file implements the url retriever for blamehangle. Plugins can send
# a message to the class defined here asking for the contents of a page
# defined by the given url, and a new thread will be spawned to go and fetch
# the data.
#
# This is done so that url requests will not cause the bot to hang if the
# remote http server responds slowly.

import asyncore
#import select
import socket
import sys
import time
import urlparse

#from Queue import *
#from thread import start_new_thread
#from threading import *
# we have our own version which doesn't mangle our User-Agent
#from classes import urllib2

from classes.Children import Child
from classes.Constants import *
from classes.Common import *

# ---------------------------------------------------------------------------

dodgy_html_check = re.compile("href='(?P<href>[^ >]+)").search

# ---------------------------------------------------------------------------

class HTTPMonster(Child):
	"""
	The HTTPMonster
	This class takes requests for URLs and fetches them in a new thread
	to ensure that the bot will not freeze due to slow servers, or whatever
	"""
	
	def setup(self):
		self.rehash()
		
		self.urls = []
		#self.threads = []
	
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
		
		#self.__stop_threads()
		#self.setup()
		#self.run_once()
	
	def noshutdown(self, message):
		self.__stop_threads()
	
	def norun_once(self):
		for i in range(self.conns):
			the_thread = Thread(target=URLThread, args=(self,i))
			self.threads.append([the_thread,0])
			the_thread.start()
			
			tolog = "Started URL thread: %s" % the_thread.getName()
			self.putlog(LOG_DEBUG, tolog)
	
	def __stop_threads(self):
		_sleep = time.sleep
		for thread in self.threads:
			thread[1] = 1
		#for i in range(len(self.threads)):
		#	self.threads[i][1] = 1
		
		# wait until all our threads have exited
		while [t for t,s in self.threads if t.isAlive()]:
			_sleep(0.25)
		
		tolog = "All URL threads stopped"
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	
	def run_always(self):
		asyncore.poll()
		
		if self.urls and len(asyncore.socket_map) < self.max_conns:
			async_http(self, self.urls.pop(0))

	# -----------------------------------------------------------------------
	
	def _message_REQ_URL(self, message):
		if len(asyncore.socket_map) < self.max_conns:
			async_http(self, message)
		else:
			self.urls.append(message)
		
		#start_new_thread(URLThread, (self, message))

# ---------------------------------------------------------------------------

class async_http(asyncore.dispatcher_with_send):
	def __init__(self, parent, message):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.data = ''
		self.header = ''
		
		self.parent = parent
		self.source = message.source
		self.returnme = message.data[0]
		self.url = message.data[1]
		
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
		
		# Fix up the path field
		if not path:
			path = '/'
		if params:
			path = '%s;%s' % (path, params)
		if query:
			path = '%s?%s' % (path, query)
		
		self.path = path
		
		# Create the socket and start the connection
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect((host, port))
	
	# Connection succeeded
	def handle_connect(self):
		text = "GET %s HTTP/1.1\r\n" % (self.path)
		self.send(text)
		text = "Host: %s\r\n" % (self.host)
		self.send(text)
		text = "User-Agent: %s\r\n" % (self.parent.user_agent)
		self.send(text)
		text = "Connection: close\r\n"
		self.send(text)
		self.send("\r\n")
	
	# An exception occured somewhere
	def handle_error(self):
		t, v, tb = sys.exc_info()
		del tb
		
		if t == 'KeyboardInterrupt':
			raise
		else:
			tolog = "Error while trying to fetch url: %s - %s" % (self.url, v)
			self.parent.putlog(LOG_ALWAYS, tolog)
		
		self.close()
	
	# Connection has data to read
	def handle_read(self):
		data = self.recv(512)
		self.data += data
		
		if not self.header:
			chunks = self.data.split('\r\n\r\n', 1)
			if len(chunks) <= 1:
				return
			
			header, data = chunks
			self.header = header
			self.data = data
			
			#print self.header.splitlines()
	
	# Connection has been closed
	def handle_close(self):
		#if self.data:
		# We have some data, might as well process it?
		self.process_data(self.data)
	
	def process_data(self, pagetext):
		if len(pagetext) > 0:
			# Dodgy HTML fix up time
			m = dodgy_html_check(pagetext)
			while m:
				pre = pagetext[:m.start()]
				post = pagetext[m.end():]
				start, end = m.span('href')
				fixed = '"' + pagetext[start:end - 1].replace("'", "%39") + '"'
				pagetext = pre + 'href=' + fixed + post
				m = dodgy_html_check(pagetext)
			
			tolog = 'Finished fetching URL: %s - %d bytes' % (self.url, len(pagetext))
			self.parent.putlog(LOG_DEBUG, tolog)
			
			data = [self.returnme, pagetext]
			#message = Message('HTTPMonster', self.source, REPLY_URL, data)
			#self.parent.outQueue.append(message)
			self.parent.sendMessage(self.source, REPLY_URL, data)
		
		self.close()

# ---------------------------------------------------------------------------

def URLThread(parent, myindex):
	_select = select.select
	_sleep = time.sleep
	_time = time.time
	
	while 1:
		# check if we have been asked to die
		if parent.threads[myindex][1]:
			return
		
		# check if there is a url waiting for us to go and get
		try:
			message = parent.urls.get_nowait()
		
		# if not, take a nap
		except Empty:
			_sleep(0.25)
			continue
		
		# we have something to do
		returnme, url = message.data
		
		tolog = 'Fetching URL: %s' % url
		parent.putlog(LOG_DEBUG, tolog)
		
		last_read = _time()
		pagetext = ''
		
		# get the page
		request = urllib2.Request(url)
		request.add_header('User-Agent', parent.user_agent)
		request.add_header('Connection', 'close')
		# Not sure if we should use these
		#request.add_header("If-Modified-Since", format_http_date(modified))
		#request.add_header("Accept-encoding", "gzip")
		
		try:
			the_page = urllib2.urlopen(request)
			
			while 1:
				try:
					can_read = _select([the_page], [], [], 1)[0]
					if can_read:
						data = the_page.read(1024)
						if len(data) == 0:
							break
					
					elif (_time() - last_read >= 15):
						raise Exception, 'transfer timed out'
					
					else:
						print "bok"
				
				except IOError:
					# Ignore IOErrors, they seem to just mean we're finished
					pass
				
				else:
					pagetext += data
					last_read = _time()
					_sleep(0.05)
		
		except Exception, why:
			# Something bad happened
			tolog = "Error while trying to fetch url: %s - %s" % (url, why)
			parent.putlog(LOG_ALWAYS, tolog)
		
		
		# XXX This shouldn't be needed, but I suspect these are hanging
		# around and not getting collected for whatever reason
		try:
			if the_page.fp:
				the_page.close()
			del the_page
		except:
			pass
		
		
		# We have some data, might as well process it?
		if len(pagetext) > 0:
			# Dodgy HTML fix up time
			m = dodgy_html_check(pagetext)
			while m:
				pre = pagetext[:m.start()]
				post = pagetext[m.end():]
				start, end = m.span('href')
				fixed = '"' + pagetext[start:end - 1].replace("'", "%39") + '"'
				pagetext = pre + 'href=' + fixed + post
				m = dodgy_html_check(pagetext)
			
			tolog = 'Finished fetching URL: %s - %d bytes' % (url, len(pagetext))
			parent.putlog(LOG_DEBUG, tolog)
			
			data = [returnme, pagetext]
			message = Message('HTTPMonster', message.source, REPLY_URL, data)
			parent.outQueue.append(message)
