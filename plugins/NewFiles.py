# ---------------------------------------------------------------------------
# $Id: GrabBT.py 4012 2006-04-06 06:32:20Z freddie $
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2007, blamehangle team
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
Watch directories for new files and announce them.
"""

import dircache
import os

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class NewFiles(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__dirs = {}
		
		for section in [s for s in self.Config.sections() if s.startswith('NewFiles.')]:
			opts = self.OptionsDict(section, autosplit=True)
			name = section.split('.')[1]
			
			self.__dirs[name] = {
				'watch_dir': opts.get('watch_dir', ''),
				'http_base': opts.get('http_base', ''),
				'spam': opts.get('spam'),
			}
			self.__dirs[name]['dircache'] = dircache.listdir(self.__dirs[name]['watch_dir'])

	
	def register(self):
		# If we have some directories to watch, start the timer
		if self.__dirs != {}:
			self.addTimedEvent(
				method = self.__Directory_Scan,
				interval = 5,
			)
	
	# -----------------------------------------------------------------------
	# It's time to see if we have any new files
	def __Directory_Scan(self, trigger):
		# Check the dircache
		for name, data in self.__dirs.items():
			files = dircache.listdir(data['watch_dir'])
			if files is data['dircache']:
				return
			
			# Spam the new files
			for filename in files:
				# Cached
				if filename in data['dircache']:
					continue
				# Hidden
				if filename.startswith('.'):
					continue
				# Not a file
				filepath = os.path.join(data['watch_dir'], filename)
				if not os.path.isfile(filepath):
					continue
				
				filesize = NiceSize(os.path.getsize(filepath))
				
				if data['http_base']:
					replytext = 'New file: %s (%s) - %s%s' % (
						filename, filesize, data['http_base'], QuoteURL(filename))
				else:
					replytext = 'New file: %s (%s)' % (filename, filesize)
				
				self.privmsg(data['spam'], None, replytext)
			
			data['dircache'] = files

# ---------------------------------------------------------------------------
