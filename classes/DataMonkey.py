
from Queue import Queue

from classes.Constants import *

from classes.Children import Child
from classes.Database import Database

# ---------------------------------------------------------------------------

class DataMonkey(Child):
	"""
	This class handles database requests, using a supposedly intelligent
	queue/return method and multiple DB threads.
	"""
	
	DBs = []
	Requests = []
	
	def setup(self):
		self.Num_Connections = self.Config.getint('database', 'connections')
		if self.Num_Connections > 0:
			for i in range(self.Num_Connections):
				db = Database(self)
				self.DBs.append(db)
			
			print self.DBs
	
	def run_sometimes(self, currtime):
		# If we have any pending requests, and a spare DB thread, action a
		# request.
		pass
	
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		stuff = message.data
		
		# stuff the request into the request queue, which will be looked at
		# next time around the _sometimes loop
		#?
