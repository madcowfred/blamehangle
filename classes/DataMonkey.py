
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
	
	def setup(self):
		options = []
		for option in ('hostname', 'username', 'password', 'database'):
			options.append(self.Config.get('database', option))
		
		for i in range(self.Config.getint('database', 'connections')):
			db = Database(*options)
			self.DBs.append(db)
	
	# A database query, be afraid
	def _message_REQ_QUERY(self, message):
		stuff = message.data
