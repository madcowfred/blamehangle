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

import select
import time

from Queue import *
#from thread import start_new_thread
from threading import *
# we have our own version which doesn't mangle our User-Agent
from classes import urllib2

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
		if self.Config.has_option('HTTP', 'useragent'):
			self.user_agent = self.Config.get('HTTP', 'useragent')
		else:
			# Default to Mozilla running in windows
			#self.user_agent = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.2.1) Gecko/20021130"
			# Default to FireBird instead
			self.user_agent = "Mozilla/5.0 (Windows; U; Windows NT 5.0; en-US; rv:1.4b) Gecko/20030516 Mozilla Firebird/0.6"
		
		# Set up our threads
		if self.Config.has_option('HTTP', 'connections'):
			conns = self.Config.getint('HTTP', 'connections')
			if conns < 1:
				conns = 1
			elif conns > 10:
				conns = 10
		else:
			conns = 2
		
		self.urls = Queue(0)
		self.threads = []
		for i in range(conns):
			the_thread = Thread(target=URLThread, args=(self,i))
			self.threads.append([the_thread,0])
			the_thread.start()
			
			tolog = "Started URL thread: %s" % the_thread.getName()
			self.putlog(LOG_DEBUG, tolog)
	
	def rehash(self):
		self.__stop_threads()
		self.setup()
	
	def shutdown(self, message):
		self.__stop_threads()
	
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
	
	def _message_REQ_URL(self, message):
		self.urls.put(message)
		#start_new_thread(URLThread, (self, message))

# ---------------------------------------------------------------------------

# Will work on this one day (fred)
#class URLThread(threading.Thread):
#	def __init__(self, parent):
#		threading.Thread.__init__(self)
#		
#		self.parent = parent
#		self.stopnow = 0
#	
#	def run(self):


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
