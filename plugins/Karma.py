#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# Karma plugin
#----------------------------------------------------------------------------

from classes.Plugin import Plugin
from classes.Constants import *
import re

class Karma(Plugin):
	"""
	Karma.
	This description will expand when there is something for it to expand
	upon
	"""
	
	__SELECT_QUERY = "SELECT key, value FROM karma WHERE key = %s"
	__INSERT_QUERY = "INSERT INTO karma VALUES ('%s',%d)"
	__UPDATE_QUERY = "UPDATE karma SET key, value = key, %d WHERE key = %s"
	
	KARMA_PLUS = "KARMA_PLUS"
	KARMA_MINUS = "KARMA_MINUS"
	KARMA_LOOKUP = "KARMA_LOOKUP"
	KARMA_MOD = "KARMA_MOD"
	
	def setup(self):
		pass

#----------------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		reply = [
		(PUBLIC, re.compile("^.*(?=\+\+$)"), [0], KARMA_PLUS),
		(PUBLIC, re.compile("^.*(?=--$)"), [0], KARMA_MINUS),
		(PUBLIC, re.compile("^karma .*(?=$|\?$)"), [0], KARMA_LOOKUP),
		(MSG, re.complie("^karma .*(?=$|\?$)"), [0], KARMA_LOOKUP)
		]
		self.sendMessage('PluginHandler', PLUGIN_REGISTER, reply)
	
#----------------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		event, [key] = message.data
		
		queryObj = whatever(__SELECT_QUERY, key, (event, key))
		self.sendMessage('TheDatabase', DB_QUERY, queryObj)
	
#----------------------------------------------------------------------------

	def _message_WHATEVER_THE_DB_SENDS_BACK(self, message):
		result, (event, key) = message.data
		
		if event == KARMA_LOOKUP:
			if result == "":
				# no karma!
				reply = "%s has neutral karma." % key
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
			else:
				key, value = result
				reply = "%s has karma of %d" % (key, value)
				self.sendMessage('PluginHandler', PLUGIN_REPLY, reply)
				
		elif event == KARMA_PLUS:
			if result == "":
				# no karma, so insert as 1
				queryObj = whatever(__INSERT_QUERY, (1, key), (KARMA_MOD, key))
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
			else:
				# increment existing karma
				key, value = result
				queryObj = whatever(__UPDATE_QUERY, (1, key), (KARMA_MOD, key))
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
				
		elif event == KARMA_MINUS:
			if result == "":
				# no karma, so insert as -1
				queryObj =  whatever(__INSERT_QUERY, (-1, key), (KARMA_MOD, key))
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)
			else:
				# decrement existing karma
				queryObj = whatever(__UPDAtE_QUERY, (-1, key) (KARMA_MOD, key))
				self.sendMessage('TheDatabase', DB_QUERY, queryObj)

		elif event == KARMA_MOD:
			# The database just made our requested modifications to the karma
			# table. We don't need to do anything about this, so just pass
			pass

		else:
			# We got a wrong message, what the fuck?
			raise ValueError, "Database sent Karma an erroneous %s" % event

#----------------------------------------------------------------------------
