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

from urllib2 import *
from Queue import Queue
from thread import start_new_thread
from threading import BoundedSemaphore

from classes.Children import Child
from classes.Constants import *
from classes.Common import *

class HTTPMonster(Child):
	"""
	The HTTPMonster
	This class takes requests for URLs and fetches them in a new thread
	to ensure that the bot will not freeze due to slow servers, or whatever
	"""

	def setup(self):
		self.Sem = BoundedSemaphore()
	
	# -----------------------------------------------------------------------

	def _message_REQ_URL(self, message):
		start_new_thread(URLThread, (self, message))

# ---------------------------------------------------------------------------

def URLThread(parent, message):
	url, returnme = message.data
	try:
		# get the page
		the_page = urlopen(url)
		pagetext = the_page.read()
	except Exception, why:
		# something borked
		parent.Sem.acquire()
		tolog = "Error while trying to fetch url: %s - %s" % (url, why)
		parent.putlog(LOG_ALWAYS, tolog)
		parent.Sem.release()
	else:
		# we have the page
		data = [pagetext, returnme]
		message = Message('HTTPMonster', message.source, REPLY_URL, data)
		parent.Sem.acquire()
		parent.outQueue.put(message)
		parent.Sem.release()
	
