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
	done = 0
	
	def __init__(self, Config):
		self.Config = Config
	
	def __connect(self):
		if self.db:
			return
		
		self.db = MySQLdb.connect(	host=self.Config.get('database', 'hostname'),
									user=self.Config.get('database', 'username'),
									passwd=self.Config.get('database', 'password'),
									db=self.Config.get('database', 'database'),
									connect_timeout=30,
									compress=1
									)
		
		self.db.paramstyle = 'format'
	
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
# outQueue -- a Queue object where we will place the query results
#             for distribution
# message  -- a message object with the query data inside
# --------------------------------------------------------------
def DataThread(parent, db, message):
	results = []
	
	ident = message.data[0]
	queries = message.data[1:]
	
	for query, args in queries:
		results.append(db.query(query, *args))
	
	message = Message('DataMonkey', message.source, ident, results)
	parent.outQueue.put(message)
	
	# Make our db object usable again
	parent.DBs.append(db)
