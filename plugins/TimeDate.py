# Copyright (c) 2003-2009, blamehangle team
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

'A huge plugin to see what the time is in various places.'

import os

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class TimeDate(Plugin):
	_HelpSection = 'time'
	
	def register(self):
		# Sorry, no timezone stuff on Windows
		if os.name == 'nt':
			self.logger.warn("Unable to get timezone information on Windows systems.")
			return
		
		self.addTextEvent(
			method = self.__Date,
			regexp = r'^date (?P<city>[\w\s]+)$',
			help = ('date', '\02date\02 <timezone> : Show the current date in <timezone>, using local system timezone data. Can be a timezone name (PST) or city (Suva, Fiji).'),
		)
	
	# -----------------------------------------------------------------------
	
	def __Date(self, trigger):
		city = trigger.match.group('city').replace(' ', '_')
		
		# Try to find our new timezone
		cmdline = 'find /usr/share/zoneinfo -iname "%s"' % city
		
		# We don't care about stdin
		p_in, p_out = os.popen2(cmdline)
		p_in.close()
		
		data = p_out.readlines()
		p_out.close()
		
		# Assume it's the first match
		if data:
			# Save the old timezone
			oldtz = os.environ.get('TZ', None)
			
			# Set the new timezone
			newtz = data[0].strip()[20:]
			os.environ['TZ'] = newtz
			
			# Get the date
			p_out = os.popen('/bin/date')
			
			data = p_out.readlines()
			p_out.close()
			
			date = data[0].strip()
			
			# Reset the old timezone
			if oldtz is None:
				del os.environ['TZ']
			else:
				os.environ['TZ'] = oldtz
			
			# Make the reply text
			replytext = '[%s] %s' % (newtz, date)
		
		# No matches, oh well
		else:
			replytext = "Unable to find timezone for '%s'" % city
		
		# Send the reply!
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
