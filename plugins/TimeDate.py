# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# A huge plugin to see what the time is in various places.

import re
import os

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

TIME_DATE = 'TIME_DATE'
DATE_RE = re.compile('^date (?P<city>\w+)$')
DATE_HELP = '\02date\02 <city> : Do something.'

# ---------------------------------------------------------------------------

class TimeDate(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		# Sorry, no windows timezone stuff
		if os.name == 'nt':
			self.putlog(LOG_WARNING, "Unable to get timezone information on Windows systems.")
			return
		
		date_dir = PluginTextEvent(TIME_DATE, IRCT_PUBLIC_D, DATE_RE)
		date_msg = PluginTextEvent(TIME_DATE, IRCT_MSG, DATE_RE)
		self.register(date_dir, date_msg)
		
		self.setHelp('time', 'date', DATE_HELP)
		
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == TIME_DATE:
			self.__Date(trigger)
	
	# -----------------------------------------------------------------------
	
	def __Date(self, trigger):
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
			p_in, p_out = os.popen2('/bin/date')
			p_in.close()
			
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
