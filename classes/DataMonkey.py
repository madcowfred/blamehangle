# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

from Queue import *
from threading import *
import time

# ---------------------------------------------------------------------------

from classes.Children import Child
from classes.Constants import *

from classes import Database

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
	
	# we start our threads here so that a plugin compile error lets us exit
	# cleanly
	def run_once(self):
		DBclass = None
		
		module = self.Config.get('database', 'module').lower()
		if module == 'mysql':
			DBclass = Database.MySQL
		elif module == 'postgres':
			DBclass = Database.Postgres
		elif module == 'sqlite':
			DBclass = Database.SQLite
		else:
			raise Exception, 'Invalid database module: %s' % module
		
		for i in range(self.conns):
			db = DBclass(self.Config)
			the_thread = Thread(target=Database.DataThread, args=(self,db,i))
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
			_sleep(0.1)
		
		tolog = "All db threads shutdown"
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		# stuff the request into the request queue, which will be looked at
		# next time around the _sometimes loop
		self.Requests.put(message)
