# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Our own abstracted database class. Does connections, variable interpolation
and turning result sets into a dictionary.
"""

import os
import sys
import time
import types

from classes.Constants import *
from classes.Message import Message

# ---------------------------------------------------------------------------

sys.path.append(os.path.expanduser('~/lib/python'))

# ---------------------------------------------------------------------------
# Base class for database wrappers
class DatabaseWrapper:
	def __init__(self, Config):
		self.Config = Config
		self.db = None
	
	def _connect(self):
		raise Exception, 'must override _connect()!'
	
	def disconnect(self):
		if self.db:
			self.db.close()
			self.db = None
	
	def query(self, sqlquery, *args):
		self._connect()
		
		cursor = self.db.cursor()
		
		if args:
			newquery = self._escape(sqlquery, args)
			cursor.execute(newquery)
		else:
			cursor.execute(sqlquery)
		
		if sqlquery.startswith('SELECT'):
			result = self._makedict(cursor.description, cursor.fetchall())
		else:
			result = long(cursor.rowcount)
		
		self.db.commit()
		
		return result
	
	def _escape(self, sqlquery, args):
		newargs = []
		
		for arg in args:
			if type(arg) in types.StringTypes:
				# escape annoying chars
				arg = arg.replace('$', '\\$')
				arg = arg.replace('\\', '\\\\')
				# double up on quotes to stop evilness
				arg = arg.replace("'", "''")
				
				arg = "'%s'" % arg
			
			# None -> NULL
			elif arg is None:
				arg = 'NULL'
			
			newargs.append(arg)
		
		return sqlquery % tuple(newargs)
	
	def _makedict(self, columns, rows):
		result = []
		
		for row in rows:
			thisrow = {}
			for i in range(len(columns)):
				arg = row[i]
				# unescape annoying chars
				if type(arg) == types.StringType:
					arg = arg.replace('\\$', '$')
					arg = arg.replace('\\\\', '\\')
				
				thisrow[columns[i][0]] = arg
			
			result.append(thisrow)
		
		return tuple(result)

# ---------------------------------------------------------------------------
# Wrapper class for MySQLdb
class MySQL(DatabaseWrapper):
	def _connect(self):
		if self.db:
			return
		
		module = __import__('MySQLdb', globals(), locals(), [])
		
		self.db = module.connect(	host=self.Config.get('database', 'hostname'),
									db=self.Config.get('database', 'database'),
									user=self.Config.get('database', 'username'),
									passwd=self.Config.get('database', 'password'),
									connect_timeout=20,
									compress=1,
									)

# ---------------------------------------------------------------------------
# Wrapper class for pyGreSQL
class Postgres(DatabaseWrapper):
	def _connect(self):
		if self.db:
			return
		
		try:
			module = __import__('pgdb', globals(), locals(), [])
		except ImportError:
			try:
				module = __import__('psycopg', globals(), locals(), [])
			except ImportError:
				raise ImportError, "No module named pgdb or psycopg"
		
		self.db = module.connect(	host=self.Config.get('database', 'hostname'),
									database=self.Config.get('database', 'database'),
									user=self.Config.get('database', 'username'),
									password=self.Config.get('database', 'password'),
								)

# ---------------------------------------------------------------------------
# Wrapper class for pyGreSQL
class SQLite(DatabaseWrapper):
	def _connect(self):
		if self.db:
			return
		
		module = __import__('sqlite', globals(), locals(), [])
		
		self.db = module.connect(self.Config.get('database', 'database'))

# ---------------------------------------------------------------------------
