# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'MapQuest.com travel distance checker.'

import re
from urllib import urlencode

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

MAPQUEST_DISTANCE = 'MAPQUEST_DISTANCE'
DISTANCE_HELP = "\02distance\02 <[city, state] or [zip]> \02to\02 <[city, state] or zip> : Look up the distance and approximate driving time between two places using MapQuest. USA and Canada only."
DISTANCE_RE = re.compile(r'^distance (?P<source>.+?)\s+to\s+(?P<dest>.+)$')

TOTAL_TIME_RE = re.compile(r'Total Est. Time:.*?</font>\s*(.*?)\s*</td>')
TOTAL_DISTANCE_RE = re.compile(r'Total Est. Distance:.*?</font>\s*(.*?)\s*</td>')

# ---------------------------------------------------------------------------

class MapQuest(Plugin):
	"""
	"distance <[city, state] or zip> to <[city, state] or zip>"
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

	def register(self):
		self.setTextEvent(MAPQUEST_DISTANCE, DISTANCE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('travel', 'distance', DISTANCE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Someone wants us to do a distance lookup
	def _trigger_MAPQUEST_DISTANCE(self, trigger):
		source = trigger.match.group('source')
		dest = trigger.match.group('dest')
		
		source_city, source_zip, source_state, source_country = self.__Get_Info(source)
		dest_city, dest_zip, dest_state, dest_country = self.__Get_Info(dest)
		
		
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
		self.urlRequest(trigger, self.__Parse_Distance, url)
	
	# -----------------------------------------------------------------------
	# Take a wild guess at what location refers to
	def __Get_Info(self, location):
		if ',' in location:
			# This is a city, not a zip code
			i = location.index(',')
			_city = location[:i]
			_zip = ''
			_state = location[i+1:].strip().upper()
			if _state in self.__canada:
				_country = 'CA'
			else:
				_country = 'US'
		else:
			# This is a zip
			_city = ''
			_zip = location
			_state = ''
			_country = ''
		
		return (_city, _zip, _state, _country)
	
	# -----------------------------------------------------------------------
	# We heard back from mapquest. yay!
	def __Parse_Distance(self, trigger, page_url, page_text):
		# Can't find a route
		if page_text.find('We are having trouble finding a route') >= 0:
			self.sendReply(trigger, 'Unable to find a route between those places!')
			return
		
		# Random errors
		_error = None
		
		# Bad ZIP code
		if page_text.find('Invalid ZIP code') >= 0:
			_error = 'Invalid ZIP code'
		# Bad state/province
		elif page_text.find('Invalid state/province') >= 0:
			_error = 'Invalid state/province'
		# Multiple locations
		elif page_text.find('Multiple cities found') >= 0:
			_error = 'Multiple cities found'
		
		# If we have an error, spit something out
		if _error is not None:
			_start = page_text.find('Enter a starting address')
			_end = page_text.find('Enter a destination address')
			
			if _start < 0 and _end < 0:
				_check = 'source and destination locations.'
			elif _start < 0:
				_check = 'source location.'
			elif _end < 0:
				_check = 'destination location.'
			else:
				_check = 'hat? Something is fucked up here.'
			
			replytext = '%s: check your %s' % (_error, _check)
			self.sendReply(trigger, replytext)
			return
		
		# Find the source and destination info
		chunks = FindChunks(page_text, 'valign=center align=left class=size12>', '</td>')
		if not chunks:
			self.sendReply(trigger, 'Failed to parse page: source/dest info.')
			return
		
		# Did we find enough chunks?
		if len(chunks) < 2:
			self.sendReply(trigger, 'Failed to parse page: not enough chunks.')
			return
		
		# Get our locations
		source_loc = StripHTML(chunks[0])[0]
		dest_loc = StripHTML(chunks[1])[0]
		
		# Find out the total time
		m = TOTAL_TIME_RE.search(page_text)
		if not m:
			self.sendReply(trigger, 'Failed to parse page: total time.')
			return
		
		total_time = m.group(1)
		
		# Find out the total distance
		m = TOTAL_DISTANCE_RE.search(page_text)
		if not m:
			self.sendReply(trigger, 'Failed to parse page: total distance.')
			return
		
		total_distance = m.group(1)
		
		# Build the output!
		distance = total_distance.replace(' miles', '\02 miles')
		replytext  = '\02%s\02 is about \02%s from \02%s\02' % (source_loc, distance, dest_loc)
		replytext += ' with an approximate driving time of \02%s\02' % (total_time)
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
