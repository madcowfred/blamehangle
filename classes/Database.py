# --------------------------------------------------------------
# $Id$
# --------------------------------------------------------------
# This file contains the Database class, which handles the DB
# communication and most of the abstraction.
# --------------------------------------------------------------

import os
import sys

from classes.Common import *
from classes.Constants import *

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
# parent  -- something with an outQueue attribute, so we can send
#            a reply
# db      -- a pre-made Database object
# message -- a message object with the data we need inside
# --------------------------------------------------------------
def DataThread(parent, db, message):
	results = []
	
	toreturn = message.data[0]
	queries = message.data[1:]
	
	for query, args in queries:
		try:
			result = db.query(query, *args)
		
		except OperationalError, msg:
			tolog = 'Database error: %s' % msg[1]
			parent.putlog(LOG_ALWAYS, tolog)
			
			results.append(())
			
			db.disconnect()
		
		else:
			results.append(db.query(query, *args))
	
	data = [results, toreturn]
	
	message = Message('DataMonkey', message.source, REPLY_QUERY, data)
	parent.outQueue.put(message)
	
	# Make our db object usable again
	parent.DBs.append(db)
