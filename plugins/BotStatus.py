# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Provides some useful/less stats about the bot.'

import os
import time

from classes.Common import NiceSize, NiceTime
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class BotStatus(Plugin):
	_HelpSection = 'misc'
	
	def register(self):
		self.addTextEvent(
			method = self.__Gather_Stats,
			regexp = r'^botstatus$',
			help = ('botstatus', '\x02botstatus\x02 : Return some useful (maybe) stats about the bot.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants some status info, go gather it.
	def __Gather_Stats(self, trigger):
		self.sendMessage('ChatterGizmo', GATHER_STATS, {'trigger': trigger})
	
	# Gathered!
	def _message_GATHER_STATS(self, message):
		data = message.data
		now = time.time()
		
		# Work out our memory and CPU usage
		cmdline = '/bin/ps u -p %s' % os.getpid()
		lines = os.popen(cmdline, 'r').readlines()
		parts = lines[1].split(None, 10)
		data['memory'] = int(parts[5])
		
		mins, secs = parts[9].split(':')
		totalsecs = (int(mins) * 60) + float(secs)
		data['cputime'] = NiceTime(totalsecs)
		
		# Make something up
		running = NiceTime(time.time() - data['started'])
		
		chans = (data['irc_chans'] == 1) and 'channel' or 'channels'
		nets = (data['irc_nets'] == 1) and 'network' or 'networks'
		queries = (data['db_queries'] == 1) and 'query' or 'queries'
		urls = (data['http_reqs'] == 1) and 'URL' or 'URLs'
		plugins = (data['plugins'] == 1) and 'plugin' or 'plugins'
		
		if data['http_bytes']:
			urls = '%s (%s)' % (urls, NiceSize(data['http_bytes']))
		
		replytext = 'I have been running for %s. I am currently in %d %s on %d %s. I have used %s of CPU time. I am using %dKB of memory. I have performed %d database %s. I have fetched %d %s. I have %d %s loaded.' % (running, data['irc_chans'], chans, data['irc_nets'], nets, data['cputime'], data['memory'], data['db_queries'], queries, data['http_reqs'], urls, data['plugins'], plugins)
		self.sendReply(message.data['trigger'], replytext)

# ---------------------------------------------------------------------------
