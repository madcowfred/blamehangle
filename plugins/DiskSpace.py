# ---------------------------------------------------------------------------
# $Id: GrabBT.py 4095 2007-11-19 01:31:45Z freddie $
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
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
Simple plugin to report available disk space.
"""

import os
import sys

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class DiskSpace(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('DiskSpace', autosplit=True)
	
	def register(self):
		self.addTextEvent(
			method = self.__Disk_Space,
			regexp = r'^diskspace$',
			IRCTypes = (IRCT_PUBLIC_D,),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants to see how much disk space we have free.
	def __Disk_Space(self, trigger):
		network = trigger.wrap.name.lower()
		chan = trigger.target.lower()
		
		if network not in self.Options['commands'] or chan not in self.Options['commands'][network]:
			tolog = "%s on %s/%s trying to see disk space." % (trigger.userinfo, network, chan)
			self.putlog(LOG_WARNING, tolog)
			return
		
		# See how much disk space we have then
		spaces = []
		
		for volume, paths in sorted(self.Options['volumes'].items()):
			if hasattr(os, 'statvfs'):
				try:
					info = os.statvfs(paths[0])
				except OSError:
					replytext = 'ERROR!'
				else:
					# block size * total blocks
					totalgb = float(info[1]) * info[2] / 1024 / 1024 / 1024
					# block size * free blocks for non-superman
					freegb = float(info[1]) * info[4] / 1024 / 1024 / 1024
					
					per = freegb / totalgb * 100
					space = '\x02[\x02%s: %.1fGB/%.1fGB (%d%%)\x02]\x02' % (volume, freegb, totalgb, per)
					spaces.append(space)
			
			else:
				cmdline = '/bin/df -k %s' % (paths[0])
				lines = os.popen(cmdline, 'r').readlines()
				parts = lines[1].split()
				
				if len(parts) >= 4:
					totalgb = float(parts[1]) / 1024 / 1024
					freegb = float(parts[3]) / 1024 / 1024
					
					per = freegb / totalgb * 100
					space = '\x02[\x02%s: %.1fGB/%.1fGB (%d%%)\x02]\x02' % (volume, freegb, totalgb, per)
					spaces.append(space)
				else:
					replytext = 'ERROR!'
		
		# Spit it out
		replytext = 'Disk space available :: %s' % (' - '.join(spaces))
		self.sendReply(trigger, replytext)
