# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Provides some useful/less stats about the bot.'

import os
import re
import time

#from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

from plugins.SmartyPants import NiceTime

# ---------------------------------------------------------------------------

BOTSTATUS = 'BOTSTATUS'
BOTSTATUS_RE = re.compile('^botstatus$')

# ---------------------------------------------------------------------------

class BotStatus(Plugin):
	def register(self):
		self.addTextEvent(
			method = self.__Gather_Stats,
			regexp = re.compile('^botstatus$'),
			help = ('misc', 'botstatus', '\x02botstatus\x02 : Return some useful (maybe) stats about the bot.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants some status info, go gather it.
	def __Gather_Stats(self, trigger):
		self.sendMessage('ChatterGizmo', GATHER_STATS, {'trigger': trigger})
	
	# Gathered!
	def _message_GATHER_STATS(self, message):
		data = message.data
		
		# Work out our memory usage
		cmdline = '/bin/ps u -p %s' % os.getpid()
		lines = os.popen(cmdline, 'r').readlines()
		parts = lines[1].split(None, 6)
		data['memory'] = int(parts[5])
		
		# Make something up
		running = NiceTime(time.time(), data['started'])
		
		chans = (data['irc_chans'] == 1) and 'channel' or 'channels'
		nets = (data['irc_nets'] == 1) and 'network' or 'networks'
		queries = (data['db_queries'] == 1) and 'query' or 'queries'
		urls = (data['http_reqs'] == 1) and 'URL' or 'URLs'
		plugins = (data['plugins'] == 1) and 'plugin' or 'plugins'
		
		replytext = 'I have been running for %s. I am currently in %d %s on %d %s. I am using %dKB of memory. I have performed %d database %s. I have fetched %d %s. I have %d %s loaded.' % (running, data['irc_chans'], chans, data['irc_nets'], nets, data['memory'], data['db_queries'], queries, data['http_reqs'], urls, data['plugins'], plugins)
		self.sendReply(message.data['trigger'], replytext)

# ---------------------------------------------------------------------------
