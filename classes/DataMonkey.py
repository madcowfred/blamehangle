# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

from Queue import *
from threading import *
#from thread import start_new_thread
import time

# ---------------------------------------------------------------------------

from classes.Children import Child
from classes.Constants import *
from classes.Database import *

# ---------------------------------------------------------------------------

class DataMonkey(Child):
	"""
	This class handles database requests, using a supposedly intelligent
	queue/return method and multiple DB threads.
	"""
	
	def setup(self):
		self.Requests = Queue(0)
		self.threads = []
		self.Last_Status = time.time()
		
		self.conns = min(1, max(10, self.Config.getint('database', 'connections')))
	
	def rehash(self):
		self.__stop_threads()
		self.setup()
		self.run_once()
	
	def shutdown(self, message):
		self.__stop_threads()
	
	def run_once(self):
		for i in range(self.conns):
			db = Database(self.Config)
			the_thread = Thread(target=DataThread, args=(self,db,i))
			self.threads.append([the_thread, 0])
			the_thread.start()
			
			tolog = "Started db thread: %s" % the_thread.getName()
			self.putlog(LOG_DEBUG, tolog)
	
	def __stop_threads(self):
		_sleep = time.sleep

		# set the flag telling each thread that we would like it to exit
		for i in range(len(self.threads)):
			self.threads[i][1] = 1

		# wait until all threads have exited
		while [t for t,s in self.threads if t.isAlive()]:
			_sleep(0.25)

		tolog = "All db threads shutdown"
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	
	#def run_sometimes(self, currtime):
	#	if (currtime - self.Last_Status) > 5:
	#		self.Last_Status = currtime
	#		
	#		#tolog = 'Requests: %d, DBs: %d' % (len(self.Requests), len(self.DBs))
	#		#self.putlog(LOG_DEBUG, tolog)
	#	
	#	# If we have any pending requests, and a spare DB connection, action
	#	# a request.
	#	if self.Requests and self.DBs:
	#		self.putlog(LOG_DEBUG, 'Actioning a request')
	#		
	#		message = self.Requests.pop(0)
	#		db = self.DBs.pop(0)
	#		
	#		start_new_thread(DataThread, (self, db, message))
	
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		# stuff the request into the request queue, which will be looked at
		# next time around the _sometimes loop
		self.Requests.put(message)
