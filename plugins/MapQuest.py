# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# MapQuest.com travel distance checker

from classes.Plugin import *
from classes.Constants import *

# not our local urllib2!
from urllib import urlencode
import re, cStringIO

MAPQUEST = "MAPQUEST"

MAPQUEST_RE = re.compile("^ *mapquest (?P<source>.+?) +to +(?P<dest>.+)$")


class MapQuest(Plugin):
	"""
	"mapquest <[city, state] or zip> to <[city, state] or zip>"
	Looks up the travel distance informtion between the given citys on
	mapquest.com and replies with the distance and estimated travel time.
	"""

	def setup(self):
		self.__canada = [
			'AB', 'BC', 'MB', 'NB', 'NF', 'NT', 'NS', 'NU', 'ON', 'PE', 'QC',
			'SK', 'YT'
			]
		self.__america = [
			'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA',
			'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
			'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
			'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
			'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
			]
	
	# -----------------------------------------------------------------------

	def _message_PLUGIN_REGISTER(self, message):
		mq_dir = PluginTextEvent(MAPQUEST, IRCT_PUBLIC_D, MAPQUEST_RE)
		mq_msg = PluginTextEvent(MAPQUEST, IRCT_MSG, MAPQUEST_RE)

		self.register(mq_dir, mq_msg)
		self.__set_help_msgs()

	def __set_help_msgs(self):
		MAPQUEST_HELP = "'\02mapquest\02 <[city, state] or [zip]> \02to\02 <[city, state] or zip>' : Look up the distance and approximate driving time between two places, using MapQuest. USA and Canada only."

		self.setHelp('travel', 'mapquest', MAPQUEST_HELP)
	
	# -----------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data

		if trigger.name == MAPQUEST:
			self.__mapquest(trigger)
		else:
			errtext = "MapQuest got a bad event: %s" % trigger.name
			raise ValueError, errtext
	
	# -----------------------------------------------------------------------

	# Someone wants us to do a mapquest lookup
	def __mapquest(self, trigger):
		source = trigger.match.group('source')
		dest = trigger.match.group('dest')

		if ',' in source:
			# This is a city, not a zip code
			i = source.index(',')
			source_city = source[:i]
			source_zip = ""
			source_state = source[i+1:].strip().upper()
		else:
			# This is a zip
			source_city = ""
			source_zip = source
			source_state = ""

		if source_state:
			if source_state in self.__canada:
				source_country = "CA"
			else:
				source_country = "US"
				
		elif re.search("[a-zA-Z]", source_zip):
			# Canadian zip codes have letters in them, US don't
			source_country = "CA"
		else:
			source_country = "US"
		
		# same stuff, but for the destination string
		if ',' in dest:
			# This is a city, not a zip code
			i = dest.index(',')
			dest_city = dest[:i]
			dest_zip = ""
			dest_state = dest[i+1:].strip().upper()
		else:
			# This is a zip
			dest_city = ""
			dest_zip = dest
			dest_state = ""

		if dest_state:
			if dest_state in self.__canada:
				dest_country = "CA"
			else:
				dest_country = "US"
				
		elif re.search("[a-zA-Z]", dest_zip):
			# Canadian zip codes have letters in them, US don't
			dest_country = "CA"
		else:
			dest_country = "US"


		tolog = "Source: %s %s %s %s" % (source_city, source_zip, source_state, source_country)
		self.putlog(LOG_DEBUG, tolog)
		tolog = "Dest: %s %s %s %s" % (dest_city, dest_zip, dest_state, dest_country)
		self.putlog(LOG_DEBUG, tolog)

		
		# We have our source and destinations parsed, build the mapquest url
		# and send off the request
		mq_query_bits = {
			'1c':source_city, '1s':source_state, '1z':source_zip, '1y':source_country,
			'2c':dest_city, '2s':dest_state, '2z':dest_zip, '2y':dest_country
			}
		mq_query_string = urlencode(mq_query_bits)

		url = "http://www.mapquest.com/directions/main.adp?go=1&do=nw&ct=NA&1ah=&1a=&1p=&"+mq_query_string+"&lr=2&x=61&y=11"

		self.urlRequest(trigger, url)
	
	# -----------------------------------------------------------------------

	# We heard back from mapquest. yay!
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data

		# Search for our info in the page MapQuest gave us
		s = cStringIO.StringIO(page_text)
		distance = None
		travel_time = None
		source_city = None
		source_state = None
		dest_city = None
		dest_state = None
		line = s.readline()
		while line:

			if line.startswith("<input type=hidden name=1c value="):
				# We found the name of the source city, according to MapQuest
				source_city = line[34:-3]
			
			elif line.startswith("<input type=hidden name=1s value="):
				# We found the name of the source state
				source_state = line[34:-3]

			elif line.startswith("<input type=hidden name=2c value="):
				# we found the name of the destination city
				dest_city = line[34:-3]
				
			elif line.startswith("<input type=hidden name=2s value="):
				dest_state = line[34:-3]

			index = line.find("Total Distance:</b> <nobr>")
			if index != -1:
				# we found the distance, yay
				distance = self.__parse(line[index:])

			index = line.find("Total Estimated Time:</b><nobr>")
			if index != -1:
				# We found the time
				travel_time = self.__parse(line[index:])

			line = s.readline()

		if not travel_time:
			# We didn't get our answer
			source = trigger.match.group('source')
			dest = trigger.match.group('dest')
			replytext = "Could not determine distance between %s and %s" % (source, dest)
		else:
			# We have our info
			source = "%s, %s" % (source_city, source_state)
			dest = "%s, %s" % (dest_city, dest_state)
			distance = distance[15:].strip()
			distance = distance.replace(" miles", "\02 miles")
			distance = distance.replace(" km", "\02 km")
			travel_time = travel_time[21:].strip()

			replytext = "\02%s\02 is about \02%s" % (source, distance)
			replytext += " from \02%s\02" % dest
			replytext += " with an approximate driving time of \02%s\02"
			replytext = replytext % travel_time


		self.sendReply(trigger, replytext)
		s.close()

	# -----------------------------------------------------------------------
	
	def __parse(self, text):
		text = re.sub("<.+?>", "", text)
		text = text.replace("&nbsp;", " ")
		if text.endswith("\n"):
			text = text[:-1]
		return text.strip()
