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
