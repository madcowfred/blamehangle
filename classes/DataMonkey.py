# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
This implements threaded database requests. For anything using a socket
connection (MySQL and Postgres so far), long operations are just a blocking
read() on the socket. We can run database requests in a thread and allow
other things to happen at the same time.
"""

import time
from Queue import Empty, Queue
from threading import Thread

from classes import Database
from classes.Children import Child
from classes.Constants import *

# ---------------------------------------------------------------------------

class DataMonkey(Child):
	def setup(self):
		self.Requests = Queue(0)
		self.threads = []
		self.Last_Status = time.time()
		
		self.__queries = 0
		
		self.rehash()
	
	def rehash(self):
		self.conns = min(1, max(10, self.Config.getint('database', 'connections')))
	
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
			t = Thread(target=DatabaseThread, args=(self,db,i))
			t.setDaemon(1)
			t.setName('Database %d' % i)
			self.threads.append([t, 0])
			t.start()
			
			tolog = 'Started DB thread: %s' % t.getName()
			self.putlog(LOG_DEBUG, tolog)
	
	def __stop_threads(self):
		_sleep = time.sleep
		
		# set the flag telling each thread that we would like it to exit
		for i in range(len(self.threads)):
			self.threads[i][1] = 1
		
		# wait until all threads have exited
		while [t for t,s in self.threads if t.isAlive()]:
			_sleep(0.1)
		
		tolog = "All DB threads halted"
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		# stuff the request into the request queue, which will be looked at
		# next time around the _sometimes loop
		self.Requests.put(message)
		self.__queries += 1
	
	# -----------------------------------------------------------------------
	# Someone wants some stats
	def _message_GATHER_STATS(self, message):
		message.data['db_queries'] = self.__queries
		
		self.sendMessage('HTTPMonster', GATHER_STATS, message.data)


# ---------------------------------------------------------------------------

def DatabaseThread(parent, db, myindex):
	_sleep = time.sleep
	
	while 1:
		# check if we have been asked to die
		if parent.threads[myindex][1]:
			return
		
		# check if there is a pending query for us to action
		try:
			message = parent.Requests.get_nowait()
		except Empty:
			_sleep(0.25)
			continue
		
		# we have a query
		trigger, method, query, args = message.data
		
		tolog = 'Query: "%s", Args: %s' % (query, repr(args))
		parent.putlog(LOG_QUERY, tolog)
		
		try:
			result = db.query(query, *args)
		
		except:
			# Log the error
			t, v = sys.exc_info()[:2]
			
			tolog = '%s - %s' % (t, v)
			parent.putlog(LOG_WARNING, tolog)
			
			result = None
			
			db.disconnect()
		
		# Return our results
		data = [trigger, method, result]
		parent.sendMessage(message.source, REPLY_QUERY, data)
		
		# Clean up
		del trigger, method, query, args, result

# ---------------------------------------------------------------------------
