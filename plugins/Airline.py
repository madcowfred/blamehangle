# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This plugin does some stuff regarding flights and airlines.
# You can lookup an airline's code, or get details on a flight number.
#
# FIXME: At some point, rewrite this to be less hideous. Too scared to do so
#        now.
# ---------------------------------------------------------------------------

import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

MAX_AIRLINE_MATCHES = 5

AIRLINE_AIRLINE = 'AIRLINE_AIRLINE'
AIRLINE_HELP = "'\02airline\02 <code>' OR '\02airline\02 <partial name>' : lookup the name for a carrier given the code, or lookup the code  for a carrier given the name (or start of the name)"
AIRLINE_RE = re.compile(r'^airline\s+(?P<airline>.+)$')

AIRLINE_AIRPORT = 'AIRLINE_AIRPORT'
AIRPORT_HELP = "\02iata\02 <code> : look up an airport by it's IATA code"
AIRPORT_RE = re.compile(r'^airport\s+(?P<code>\w+)$')
AIRPORT_URL = 'http://www.flymig.com/iata/r/%s.htm'

AIRLINE_FLIGHT = 'AIRLINE_FLIGHT'
FLIGHT_HELP = "'\02flight\02 <code> <flight number> <date>' : look up the details of the specified flight. date is in YYYY-MM-DD format, and is optional (defaults to today's date if ommitted)"
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
	Does airline stuff?
	"""
	
	def setup(self):
		config_dir = self.Config.get('plugin', 'config_dir')
		self.Airlines = self.loadPickle('aircodes.data') or {}
		if self.Airlines:
			tolog = 'Loaded %d carriers from aircodes.data' % len(self.Airlines)
			self.putlog(LOG_DEBUG, tolog)
	
	def rehash(self):
		self.setup()
	
	# --------------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		self.setTextEvent(AIRLINE_AIRLINE, AIRLINE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(AIRLINE_AIRPORT, AIRPORT_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(AIRLINE_FLIGHT, FLIGHT_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('travel', 'airline', AIRLINE_HELP)
		self.setHelp('travel', 'airport', AIRPORT_HELP)
		self.setHelp('travel', 'flight', FLIGHT_HELP)
		self.registerHelp()
	
	# --------------------------------------------------------------------------
	# Someone wants to lookup an airline. If they gave us the code, we'll find
	# the name string, if they gave us a name string, we'll try to find codes
	# that match it
	def _trigger_AIRLINE_AIRLINE(self, trigger):
		match = self.__Airline_Search(trigger)
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
	def __Airline_Search(self, trigger):
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
	# Someone wants to look up an IATA code
	def _trigger_AIRLINE_AIRPORT(self, trigger):
		code = trigger.match.group('code').upper()
		
		# IATA codes are 3 letters
		if len(code) == 3:
			url = AIRPORT_URL % code
			self.urlRequest(trigger, self.__Parse_IATA, url)
		
		# Someone is stupid
		else:
			replytext = "'%s' is not a valid IATA code!" % code
			self.sendReply(trigger, replytext)
	
	# Site replied
	def __Parse_IATA(self, trigger, page_text):
		code = trigger.match.group('code').upper()
		page_text = page_text.replace('&deg;', '°')
		
		# 404 error
		if page_text.find('Requested File was not found') >= 0:
			replytext = "No such IATA code: '%s'" % code
			self.sendReply(trigger, replytext)
		
		# Find the chunk we need
		chunk = FindChunk(page_text, '<PRE>', '</PRE>')
		if not chunk:
			self.putlog(LOG_WARNING, 'IATA page parsing failed: no data')
			self.sendReply(trigger, 'Failed to parse page.')
			return
		
		# Split it into lines
		lines = StripHTML(chunk)
		
		# Split each line into data
		data = {}
		
		for line in lines:
			# Find the key
			n = line.find(': .')
			key = line[:n]
			
			# Find the value
			n = line.find('. ')
			data[key] = line[n+2:]
		
		# Build our output
		if 'Country' in data:
			loctext = '%s, %s' % (data['Country'], data['Airport'])
		else:
			loctext = data['Airport']
		
		parts = []
		for key in ('IATA', 'ICAO', 'Latitude', 'Longitude', 'Elevation'):
			if key in data:
				part = '\02[\02%s: %s\02]\02' % (key, data[key])
				parts.append(part)
		
		# If we had some data, spit it out now
		if parts:
			replytext = '%s :: %s' % (loctext, ' '.join(parts))
		else:
			replytext = 'No data found!'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up info on a flight.
	def _trigger_AIRLINE_FLIGHT(self, trigger):
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
		self.urlRequest(trigger, self.__Parse_Travelocity, url)
	
	# -----------------------------------------------------------------------
	# Travelocity has replied
	def __Parse_Travelocity(self, trigger, page_text):
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
