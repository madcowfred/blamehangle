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

"""
This plugin does some stuff regarding flights and airlines. You can lookup
an airline's code, or get details on a flight number.
"""

import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

MAX_AIRLINE_MATCHES = 5

FLIGHT_URL = "http://dps1.travelocity.com/dparflifo.ctl?CMonth=%s&CDayOfMonth=%s&CYear=%s&LANG=EN&last_pgd_page=dparrqst.pgd&dep_arpname=&arr_arp_name=&dep_dt_mn_1=%s&dep_dt_dy_1=%s&dep_tm1=12%%3A00pm&aln_name=%s&flt_num=%s&Search+Now.x=89&Search+Now.y=4"
IATA_URL = 'http://www.flymig.com/iata/r/%s.htm'

# ---------------------------------------------------------------------------

class Airline(Plugin):
	_HelpSection = 'travel'
	
	def setup(self):
		# Load our airline codes
		self.Airlines = {}
		
		filename = os.path.join('data', 'airline_codes')
		try:
			code_file = open(filename, 'r')
		except IOError:
			self.putlog(LOG_WARNING, "Can't find data/airline_codes!")
			return
		
		for line in code_file:
			line = line.strip()
			if not line:
				continue
			
			code, airline = line.split(None, 1)
			self.Airlines[code] = airline
		
		code_file.close()
	
	def rehash(self):
		self.setup()
	
	# --------------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__Airline_Search,
			regexp = re.compile(r'^airline\s+(?P<airline>.+)$'),
			help = ('airline', "\02airline\02 <code> OR <partial name> : Look up the name for a carrier given the code, or look up the code for a carrier given the name (or part of the name)."),
		)
		self.addTextEvent(
			method = self.__Fetch_IATA,
			regexp = re.compile(r'^iata\s+(?P<code>\w+)$'),
			help = ('iata', "\02iata\02 <code> : Look up an airport by it's IATA code."),
		)
		# This is really quite horrible :(
		f1 = "^ *flight +"
		f2 = "(?P<code>[^ ]+)"
		f3 = " +(?P<flight>[^ ]+)"
		f4 = "(( *$)|( +%s *$))"
		f5 = "(?P<year>20[0-9][0-9])-"
		f6 = "(?P<month>(0[1-9])|(1[0-2]))-"
		f7 = "(?P<day>(0[1-9])|([12][0-9])|(3[0-1]))"
		f8 = f5+f6+f7
		f9 = f4 % f8
		
		self.addTextEvent(
			method = self.__Fetch_Flight,
			regexp = re.compile(f1+f2+f3+f9),
			help = ('flight', "\02flight\02 <code> <flight number> <date> : Look up the details of the specified flight. Date is in YYYY-MM-DD format, and is optional (defaults to today's date if omitted)."),
		)
	
	# --------------------------------------------------------------------------
	# Someone wants to lookup an airline. If they gave us the code, we'll find
	# the name string, if they gave us a name string, we'll try to find codes
	# that match it
	def __Airline_Search(self, trigger):
		matches = self.__Airline_Lookup(trigger)
		replytext = "Airline search for '%s'" % trigger.match.group('airline')
		if matches:
			if len(matches) > MAX_AIRLINE_MATCHES:
				replytext += " returned too many results. Please refine your query"
			else:
				if len(matches) > 1:
					replytext += " (\02%d\02 results): " % len(matches)
				else:
					replytext += ": "
				replytext += ", ".join(["\02%s\02 - \02%s\02" % (code, name) for code, name in matches])
		else:
			replytext += " returned no results"
		self.sendReply(trigger, replytext)
	
	# --------------------------------------------------------------------------
	# Lookup the given carrier name or code. If a partial name is supplied,
	# return all the carriers that matched.
	def __Airline_Lookup(self, trigger):
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
	def __Fetch_IATA(self, trigger):
		code = trigger.match.group('code').upper()
		
		# IATA codes are 3 letters
		if len(code) == 3:
			url = IATA_URL % code
			self.urlRequest(trigger, self.__Parse_IATA, url)
		
		# Someone is stupid
		else:
			replytext = "'%s' is not a valid IATA code!" % code
			self.sendReply(trigger, replytext)
	
	# Site replied
	def __Parse_IATA(self, trigger, resp):
		code = trigger.match.group('code').upper()
		resp.data = resp.data.replace('&deg;', '\xb0')
		
		# Page not found.. but it's not a 404 :|
		if resp.data.find('Requested File was not found') >= 0:
			replytext = "No such IATA code: '%s'" % code
			self.sendReply(trigger, replytext)
			return
		
		# Find the chunk we need
		chunk = FindChunk(resp.data, '<PRE>', '</PRE>')
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
	def __Fetch_Flight(self, trigger):
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
		url = FLIGHT_URL % (month, day, year, monthtxt, day, code, flight)
		self.urlRequest(trigger, self.__Parse_Travelocity, url)
	
	# -----------------------------------------------------------------------
	# Travelocity has replied
	def __Parse_Travelocity(self, trigger, resp):
		# No results
		if resp.data.find('No match found') >= 0:
			replytext = 'Unable to find flight information'
			self.sendReply(trigger, replytext)
		
		else:
			# Find the chunk of data we're interested in
			chunk = FindChunk(resp.data, '<table name=flight_info', '</table')
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
