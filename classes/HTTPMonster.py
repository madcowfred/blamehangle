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

from Queue import Queue
from select import select
from thread import start_new_thread
from time import sleep
# we have our own version so we can mess with the user-agent string
from classes.urllib2 import urlopen

from classes.Children import Child
from classes.Constants import *
from classes.Common import *

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
			self.user_agent = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.2.1) Gecko/20021130"
	# -----------------------------------------------------------------------
	
	def _message_REQ_URL(self, message):
		start_new_thread(URLThread, (self, message))

# ---------------------------------------------------------------------------

def URLThread(parent, message):
	url, returnme = message.data
	try:
		# get the page
		the_page = urlopen(url, parent.user_agent)
		
		pagetext = ''
		while 1:
			can_read = select([the_page], [], [], 1)[0]
			if can_read:
				data = the_page.read(1024)
				if len(data) == 0:
					break
				pagetext += data
				
				sleep(0.05)
	
	except Exception, why:
		# something borked
		tolog = "Error while trying to fetch url: %s - %s" % (url, why)
		parent.putlog(LOG_ALWAYS, tolog)
	
	else:
		# we have the page
		m = dodgy_html_check(pagetext)
		while m:
			pre = pagetext[:m.start()]
			post = pagetext[m.end():]
			start, end = m.span('href')
			fixed = '"' + pagetext[start:end - 1].replace("'", "%39") + '"'
			pagetext = pre + 'href=' + fixed + post
			m = dodgy_html_check(pagetext)

		data = [pagetext, returnme]
		message = Message('HTTPMonster', message.source, REPLY_URL, data)
		parent.outQueue.put(message)
