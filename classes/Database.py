# --------------------------------------------------------------
# $Id$
# --------------------------------------------------------------
# This file contains the Database class, which handles the DB
# communication and most of the abstraction.
# --------------------------------------------------------------

import os
import sys

from classes.Common import *

# --------------------------------------------------------------

sys.path.append(os.path.expanduser('~/lib/python'))

import MySQLdb
from _mysql_exceptions import OperationalError
from MySQLdb.cursors import DictCursor

# --------------------------------------------------------------

MYSQL_ERROR_LOST_CONNECTION = 2013

# --------------------------------------------------------------
# Wrapper class for 'simple' database access.
# --------------------------------------------------------------
class Database:
	db = None
	
	def __init__(self, parent):
		self.parent = parent
		
		self.db = None
		self.done = 0
	
	def __connect(self):
		if self.db:
			return
		
		self.db = MySQLdb.connect(	host=self.parent.Config.get('database', 'hostname'),
									user=self.parent.get('database', 'username'),
									passwd=self.parent.Config.get('database', 'password'),
									db=self.parent.Config.get('database', 'database'),
									connect_timeout=30,
									compress=1
									)
		
		self.db.paramstyle = 'format'
	
	# Disconnect from the database if we're connected. Is this ever used?
	def disconnect(self):
		if self.db:
			self.db.close()
			self.db = None
	
	def query(self, query, *args):
		self.__connect()
		
		cursor = self.db.cursor(DictCursor)
		if args:
			cursor.execute(query, args)
		else:
			cursor.execute(query)
		
		if query.startswith('SELECT'):
			result = cursor.fetchall()
		else:
			result = cursor.rowcount
		
		self.db.commit()
		return result

# --------------------------------------------------------------
# A thread wrapper around the Database object.
#
# Config   -- a ConfigParser object
# outQueue -- a Queue object to write the results too
# queries  -- a list of some kind of query/data pairs
# --------------------------------------------------------------
def database_thread(Config, outQueue, ident, queries):
	results = []
	
	db = Database(Config)
	
	for query, args in queries:
		results.append(db.query(query, *args))
	
	db.disconnect()
	
	message = Message('Database', '<reply>', ident, results)
	outQueue.put(message)
