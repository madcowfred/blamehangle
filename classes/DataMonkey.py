
from Queue import Queue
from thread import start_new_thread
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
	
	DBs = []
	Requests = []
	
	Last_Status = time.time()
	
	def setup(self):
		self.Num_Connections = self.Config.getint('database', 'connections')
		if self.Num_Connections > 0:
			for i in range(self.Num_Connections):
				db = Database(self.Config)
				self.DBs.append(db)
			
			print self.DBs
	
	def run_sometimes(self, currtime):
		if (currtime - self.Last_Status) > 5:
			self.Last_Status = currtime
			
			tolog = 'Requests: %d, DBs: %d' % (len(self.Requests), len(self.DBs))
			self.putlog(LOG_DEBUG, tolog)
		
		# If we have any pending requests, and a spare DB connection, action
		# a request.
		if self.Requests and self.DBs:
			self.putlog(LOG_DEBUG, 'Actioning a request')
			
			message = self.Requests.pop(0)
			db = self.DBs.pop(0)
			
			start_new_thread(DataThread, (self, db, message))
	
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		# stuff the request into the request queue, which will be looked at
		# next time around the _sometimes loop
		self.Requests.append(message)
