# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This plugin does some stuff regarding flights and airlines.
# You can lookup an airline's code, or get details on a flight number.
# ---------------------------------------------------------------------------

from classes.Plugin import *
from classes.Constants import *
from cStringIO import *
import re, time, types, cPickle

AIRLINE_LOOKUP = "AIRLINE_LOOKUP"
FLIGHT_SEARCH = "FLIGHT_SEARCH"

AIRLINE_RE = re.compile("^ *airline +(?P<airline>.+)$")

MAX_AIRLINE_MATCHES = 5

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
		air_dir = PluginTextEvent(AIRLINE_LOOKUP, IRCT_PUBLIC_D, AIRLINE_RE)
		air_msg = PluginTextEvent(AIRLINE_LOOKUP, IRCT_MSG, AIRLINE_RE)
		fl_dir = PluginTextEvent(FLIGHT_SEARCH, IRCT_PUBLIC_D, FLIGHT_RE)
		fl_msg = PluginTextEvent(FLIGHT_SEARCH, IRCT_MSG, FLIGHT_RE)

		self.register(air_dir, air_msg, fl_dir, fl_msg)
	
	# --------------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == AIRLINE_LOOKUP:
			self.__airline_lookup(trigger)
		elif trigger.name == FLIGHT_SEARCH:
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

# ---------------------------------------------------------------------------

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
		self.sendMessage('HTTPMonster', REQ_URL, [url, trigger])
	
	# -----------------------------------------------------------------------
	
	# Travelocity has replied
	def _message_REPLY_URL(self, message):
		page_text, trigger = message.data
		
		# this ugly parsing is ripped right from the pinky java.
		# .. much like the rest of this plugin, really
		#
		# There is most likely a better way to do this, but this "works" so
		# I'll leave it for now
		s = StringIO(page_text)
		found = 0
		line = s.readline()
		while line:
			if line.lower() == "<td valign=top align=right nowrap><b>city:</b>&nbsp;</td>\n":
				line = s.readline()
				source = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_sched = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_sched = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_act = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_act = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_gate = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_gate = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				dest_bags = self.__rip(line)

				found = 1

				# Should this plugin always reply to successful queries in
				# a /msg? If so, the hack below is required
				#trigger.event.IRCType = IRCT_MSG

				# Build our reply string, and send it back to IRC!
				replytext = "\02Departure\02: %s - %s (%s) Gate: %s" % (source, source_sched, source_act, source_gate)
				replytext += " --> \02Arrival\02: %s - %s (%s) Gate: %s Baggage: %s" % (dest, dest_sched, dest_act, dest_gate, dest_bags)
				self.sendReply(trigger, replytext)

			# Keep looking for results
			line = s.readline()
		
		
		# end of while loop
		
		if not found:
			replytext = "Error finding flight"
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------

	# Rip all the HTML out of the lines that we get from travelocity
	def __rip(self, text):
		text = re.sub("<.+?>", "", text)
		text = re.sub("&nbsp;", " ", text)
		return text[:-1]

	# -----------------------------------------------------------------------
	
