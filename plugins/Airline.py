# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This plugin does some stuff regarding flights and airlines.
# You can lookup an airline's code, or get details on a flight number.
# ---------------------------------------------------------------------------

import re
import time
import types
import cPickle

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

MAX_AIRLINE_MATCHES = 5

AIRLINE_AIRLINE = 'AIRLINE_AIRLINE'
AIRLINE_HELP = "'\02airline\02 <code>' OR '\02airline\02 <partial name>' : lookup the name for a carrier given the code, or lookup the code  for a carrier given the name (or start of the name)"
AIRLINE_RE = re.compile("^airline +(?P<airline>.+)$")

AIRLINE_FLIGHT = 'AIRLINE_FLIGHT'
FLIGHT_HELP = "'\02flight\02 <code> <flight number> <date>' : Lookup the details of the specified flight. date is in YYYY-MM-DD format, and is optional (defaults to today's date if ommitted)"
# what a bastard this was to get right. god damn i hate regexps.
f1 = "^ *flight +"
f2 = "(?P<code>[^ ]+)"
f3 = " +(?P<flight>[^ ]+)"
f4 = "(( *$)|( +%s *$))"
f5 = "(?P<year>20[0-9][0-9])-"
f6 = "(?P<month>(0[1-9])|(1[0-2]))-"
f7 = "(?P<day>(0[1-9])|([12][0-9])|(3[0-1]))"
f8 = f5+f6+f7
f9 = f4 % f8

FLIGHT_RE = re.compile(f1+f2+f3+f9)

# ---------------------------------------------------------------------------

class Airline(Plugin):
	"""
	stuff. it's 6:30am.

	and it was much later when i finished.
	comments come later
	"""
	
	def setup(self):
		config_dir = self.Config.get('plugin', 'config_dir')
		self.Airlines = {}
		try:
			f = file(config_dir + "aircodes.data", "rb")
		except:
			tolog = "couldn't open %saircodes.data! Airlines plugin will not work as intended" % config_dir
			self.putlog(LOG_WARNING, tolog)
		else:
			try:
				self.Airlines = cPickle.load(f)
			except:
				tolog = "error loading data from %saircodes.data! Airlines plugin will not work as intended" % config_dir
				self.putlog(LOG_WARNING, tolog)
			else:
				f.close()
				tolog = "loaded %d carriers from %saircodes.data" % (len(self.Airlines), config_dir)
				self.putlog(LOG_DEBUG, tolog)
	
	def _message_REQ_REHASH(self, message):
		self.setup()
	
	# --------------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		air_dir = PluginTextEvent(AIRLINE_AIRLINE, IRCT_PUBLIC_D, AIRLINE_RE)
		air_msg = PluginTextEvent(AIRLINE_AIRLINE, IRCT_MSG, AIRLINE_RE)
		fl_dir = PluginTextEvent(AIRLINE_FLIGHT, IRCT_PUBLIC_D, FLIGHT_RE)
		fl_msg = PluginTextEvent(AIRLINE_FLIGHT, IRCT_MSG, FLIGHT_RE)
		
		self.register(air_dir, air_msg, fl_dir, fl_msg)
		
		self.setHelp('travel', 'airline', AIRLINE_HELP)
		self.setHelp('travel', 'flight', FLIGHT_HELP)
		
		self.registerHelp()
	
	# --------------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == AIRLINE_AIRLINE:
			self.__airline_lookup(trigger)
		elif trigger.name == AIRLINE_FLIGHT:
			self.__flight_search(trigger)
	
	# --------------------------------------------------------------------------
	# Someone wants to lookup an airline. If they gave us the code, we'll find
	# the name string, if they gave us a name string, we'll try to find codes
	# that match it
	def __airline_lookup(self, trigger):
		match = self.__airline_search(trigger)
		replytext = "Airline search for '%s'" % trigger.match.group('airline')
		if match:
			if len(match) > MAX_AIRLINE_MATCHES:
				replytext += " returned too many results. Please refine your query"
			else:
				if len(match) > 1:
					replytext += " (\02%d\02 results): " % len(match)
				else:
					replytext += ": "
				replytext += ", ".join(["\02%s\02 - \02%s\02" % (code, name) for code, name in match])
		else:
			replytext += " returned no results"
		self.sendReply(trigger, replytext)
	
	# --------------------------------------------------------------------------

	# Lookup the given carrier name or code. If a partial name is supplied,
	# return all the carriers that matched.
	def __airline_search(self, trigger):
		airtext = trigger.match.group('airline')
		if len(airtext) == 2:
			airtext = airtext.upper()
			# this is a code
			if airtext in self.Airlines:
				return [(airtext, self.Airlines[airtext])]
		else:
			# this is a name
			airtext = airtext.lower()
			matches = []
			for code, name in self.Airlines.items():
				if name.lower().startswith(airtext):
					matches.append((code, self.Airlines[code]))

			return matches
	
	# -----------------------------------------------------------------------
	
	# Someone wants to look up info on a flight.
	def __flight_search(self, trigger):
		code = trigger.match.group('code').upper()
		flight = trigger.match.group('flight')
		
		# validate the carrier code
		if not code in self.Airlines:
			replytext = "%s is not a valid airline carrier code" % code
			self.sendReply(trigger, replytext)
			return
		
		# validate that they gave us a number to search for, and not "gnashuus"
		try:
			flight_num = int(flight)
		except ValueError:
			replytext = "\02'%s'\02 is not a valid number" % flight
			self.sendReply(trigger, replytext)
			return
		
		# did they supply a date? If so, use that for the query, otherwise use
		# today's date
		try:
			year = trigger.match.group('year')
			month = int(trigger.match.group('month'))
			day = trigger.match.group('day')
		except:
			currtime = time.localtime()
			year = currtime[0]
			month = currtime[1]
			day = currtime[2]
		
		# we have all the bits we need
		mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
			"Sep", "Oct", "Nov", "Dec" ]
		monthtxt = mon[month-1]
		
		# Make the query url to send to travelocity.
		url = "http://dps1.travelocity.com/dparflifo.ctl?CMonth=%s&CDayOfMonth=%s&CYear=%s&LANG=EN&last_pgd_page=dparrqst.pgd&dep_arpname=&arr_arp_name=&dep_dt_mn_1=%s&dep_dt_dy_1=%s&dep_tm1=12%%3A00pm&aln_name=%s&flt_num=%s&Search+Now.x=89&Search+Now.y=4" % (month, day, year, monthtxt, day, code, flight)
		self.urlRequest(trigger, url)
	
	# -----------------------------------------------------------------------
	# Travelocity has replied
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == AIRLINE_FLIGHT:
			# No results
			if page_text.find('No match found') >= 0:
				replytext = 'Unable to find flight information'
				self.sendReply(trigger, replytext)
			
			else:
				# Find the chunk of data we're interested in
				chunk = FindChunk(page_text, '<table name=flight_info', '</table')
				if chunk is None:
					self.putlog(LOG_WARNING, 'Flight page parsing failed: unable to find data')
					self.sendReply(trigger, 'Failed to parse page properly')
					return
				lines = StripHTML(chunk)
				
				# Get our data!
				source = lines[3]
				dest = lines[4]
				
				source_sched = lines[6]
				dest_sched = lines[7]
				
				source_act = lines[9]
				dest_act = lines[10]
				
				source_gate = lines[12]
				dest_gate = lines[13]
				
				dest_bags = lines[15]
				
				# Should this plugin always reply to successful queries in
				# a /msg? If so, the hack below is required
				#trigger.event.IRCType = IRCT_MSG
				
				# Build our reply string, and send it back to IRC!
				replytext = "\02Departure\02: %s - %s (%s) Gate: %s" % (source, source_sched, source_act, source_gate)
				replytext += " --> \02Arrival\02: %s - %s (%s) Gate: %s Baggage: %s" % (dest, dest_sched, dest_act, dest_gate, dest_bags)
				self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
