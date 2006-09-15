# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2006, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
This implements threaded database requests. For anything using a socket
connection (MySQL and Postgres so far), long operations are just a blocking
read() on the socket. We can run database requests in a thread and allow
other things to happen at the same time.
"""

import sys
import time

from Queue import Empty, Queue
from threading import Lock, Thread

from classes import Database
from classes.Children import Child
from classes.Constants import *

# ---------------------------------------------------------------------------

class DataMonkey(Child):
	def setup(self):
		self.__queries = 0
		self.__threads = []
		self.Requests = Queue(0)
		
		self.num_conns = max(1, min(10, self.Config.getint('database', 'connections')))
	
	def shutdown(self, message):
		self.__Stop_Threads()
	
	# -----------------------------------------------------------------------
	# Start our threads just after we are created so an error here lets us
	# shut down cleanly
	def run_once(self):
		self.__Start_Threads()
	
	# Start our configured amount of threads
	def __Start_Threads(self):
		# Decide what database class we're meant to use
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
		
		# Start the thread objects
		parentlock = Lock()
		for i in range(self.num_conns):
			t = DatabaseThread(self, parentlock, self.Requests, DBclass(self.Config))
			t.setName('db%02d' % i)
			t.start()
			self.__threads.append(t)
		
		tolog = 'Started %d database thread(s)' % (self.num_conns)
		self.putlog(LOG_ALWAYS, tolog)
	
	# Stop our threads
	def __Stop_Threads(self):
		# Tell all of our threads to exit
		for i in range(self.num_conns):
			self.Requests.put(None)
		
		# Wait until all threads have stopped
		for t in self.__threads:
			t.join()
		
		tolog = 'All database threads halted'
		self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	# Someone wants some stats
	def _message_GATHER_STATS(self, message):
		message.data['db_queries'] = self.__queries
		
		self.sendMessage('HTTPMonster', GATHER_STATS, message.data)
	
	# -----------------------------------------------------------------------
	# A database query, add it to the request queue
	def _message_REQ_QUERY(self, message):
		self.Requests.put(message)
		self.__queries += 1

# ---------------------------------------------------------------------------

class DatabaseThread(Thread):
	def __init__(self, parent, ParentLock, Requests, db):
		Thread.__init__(self)
		self.parent = parent
		self.ParentLock = ParentLock
		self.Requests = Requests
		self.db = db
	
	def run(self):
		while True:
			message = self.Requests.get()
			# None = die
			if message is None:
				print 'dying!'
				return
			
			trigger, method, query, args = message.data
			
			newquery = tolog = None
			try:
				newquery, result = self.db.query(query, *args)
			except:
				# Log the error
				t, v = sys.exc_info()[:2]
				tolog = '%s - %s' % (t, v)
				
				result = None
				
				self.db.disconnect()
			
			# Return the results and maybe log something
			self.ParentLock.acquire()
			
			if newquery is not None:
				self.parent.putlog(LOG_QUERY, newquery)
			if tolog is not None:
				self.parent.putlog(LOG_WARNING, tolog)
			data = [trigger, method, result]
			self.parent.sendMessage(message.source, REPLY_QUERY, data)
			
			self.ParentLock.release()
			
			# Clean up temporary crap
			del message, trigger, method, query, args, newquery, tolog, result

# ---------------------------------------------------------------------------
