# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004, MadCowDisease
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
		
		try:
			result = db.query(parent.putlog, query, *args)
		
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
