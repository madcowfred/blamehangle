# --------------------------------------------------------------
# $Id$
# --------------------------------------------------------------
# This file contains the Database class, which handles the DB
# communication and most of the abstraction.
# --------------------------------------------------------------

import os
import sys
from Queue import *

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
# myindex -- an index into parent.threads for the item describing
#            this thread
# --------------------------------------------------------------
def DataThread(parent, db, myindex):
	_sleep = time.sleep

	while 1:
		# check if we have been asked to die
		if parent.threads[myindex][1]:
			return
	
		# check if there is a pending query for us to action
		try:
			message = parent.Requests.get_nowait()
	
		# if not, zzzzzz
		except Empty:
			_sleep(0.25)
		
		# we have a query
		else:
			parent.putlog(LOG_DEBUG, 'Actioning a request')
			results = []
			toreturn, queries = message.data
			
			for chunk in queries:
				query = chunk[0]
				# If there's any args, use them
				if len(chunk) >= 2:
					if type(chunk[1]) in (types.ListType, types.TupleType):
						args = chunk[1]
					else:
						args = chunk[1:]
				# No args!
				else:
					args = []
				
				#tolog = 'Query: %s, Args: %s' % (query, args)
				#parent.putlog(LOG_DEBUG, tolog)
				
				try:
					result = db.query(query, *args)
				
				except OperationalError, msg:
					tolog = 'Database error: %s' % msg[1]
					parent.putlog(LOG_ALWAYS, tolog)
					
					results.append(())
					
					db.disconnect()
				
				else:
					results.append(result)
			
			data = [toreturn, results]
			
			message = Message('DataMonkey', message.source, REPLY_QUERY, data)
			parent.outQueue.append(message)
