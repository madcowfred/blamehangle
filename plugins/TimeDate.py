# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'A huge plugin to see what the time is in various places.'

import os
import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

TIME_DATE = 'TIME_DATE'
DATE_HELP = '\02date\02 <timezone> : Show the current date in <timezone>, using local system timezone data. Can be a timezone name (PST) or city (Fiji).'
DATE_RE = re.compile('^date (?P<city>\w+)$')

# ---------------------------------------------------------------------------

class TimeDate(Plugin):
	def register(self):
		# Sorry, no windows timezone stuff
		if os.name == 'nt':
			self.putlog(LOG_WARNING, "Unable to get timezone information on Windows systems.")
			return
		
		self.setTextEvent(TIME_DATE, DATE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('time', 'date', DATE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _trigger_TIME_DATE(self, trigger):
		city = trigger.match.group('city')
		
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
