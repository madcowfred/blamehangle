# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Retrieve current weather data from the Australian Bureau of Meteorology.'

import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin, PluginFakeTrigger

# ---------------------------------------------------------------------------
# Tuples of 'products'. Should be (product name, page code, priority). If a
# location is listed on more than one page, the _lowest_ priority one will be
# used. Useful for the big pages that only update hourly.
PRODUCTS = (
	# NSW
	('Sydney', 'IDN65066', 0),
	('NSW', 'IDN65091', 1),
	# QLD
	('Brisbane', 'IDQ65113', 0),
	('North Queensland', 'IDQ60600', 1),
	('Western Queensland', 'IDQ60601', 1),
	('Central Queensland', 'IDQ60602', 1),
	('Southeast Queensland', 'IDQ60603', 1),
	# SA
	('Adelaide', 'IDS65012', 0),
	('South Australian', 'IDS65013', 1),
	# TAS
	('Hobart', 'IDT65012', 0),
	# VIC
	('Melbourne', 'IDV60034', 0),
	('Victoria', 'IDV65119', 1),
	# WA
	('Perth', 'IDW60034', 0),
	('Western Australian', 'IDW60199', 1),
)

TITLE_RE = re.compile('<title>(.*?)</title>', re.I)

TITLE_REs = (
	re.compile('^Current (.+) Observations.*$'),
	re.compile('^Current Observations for (.+) Forecast Districts$'),
	re.compile('^Hourly Data from (\S+) AWS$'),
	re.compile('^Hourly AWS Observations - (.+)$'),
)

MONTH = 60 * 60 * 24 * 30

# ---------------------------------------------------------------------------

AUSBOM_URL = 'http://www.bom.gov.au/products/%s.shtml'

# ---------------------------------------------------------------------------

class AusBOM(Plugin):
	_HelpSection = 'weather'
	
	def setup(self):
		self.__updating = 0
		
		self.rehash()
	
	def rehash(self):
		# Load our location data from the pickle.
		self.__Locations = self.loadPickle('.ausbom.locations')
		# If there isn't any, trigger an update.
 		if self.__Locations is None and not self.__updating:
			self.__Update_Locations()
		# If there is, and it's more than a month old, update
		elif time.time() - self.__Locations['_updated_'] > MONTH:
			self.__Update_Locations()
	
	# -----------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_AusBOM,
			regexp = re.compile('^ausbom (?P<location>.+)$'),
			help = ('ausbom', '\02ausbom\02 <location> : Get current weather data for <location>.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants some info on a location
	def __Fetch_AusBOM(self, trigger):
		product = self.__Find_Product(trigger, trigger.match.group('location'))
		if product:
			url = AUSBOM_URL % (product)
			self.urlRequest(trigger, self.__Parse_Current, url)
	
	# -----------------------------------------------------------------------
	# Send URL requests for updating
	def __Update_Locations(self):
		self.putlog(LOG_ALWAYS, 'AusBOM: Updating location data...')
		
		# Reset the location data
		self.__Locations = {}
		
		# We need a fake trigger here for urlRequest()
		trigger = PluginFakeTrigger('AUSBOM_UPDATE')
		trigger.count = 0
		
		# Go to get the first one
		url = AUSBOM_URL % PRODUCTS[0][1]
		self.urlRequest(trigger, self.__Parse_Current, url)
	
	# -----------------------------------------------------------------------
	# Parse a Current Observations page.
	def __Parse_Current(self, trigger, resp):
		# Work out what our location should be
		if trigger.name == '__Fetch_AusBOM':
			location = trigger.match.group('location')
		elif trigger.name == 'AUSBOM_UPDATE':
			location = None
		
		# Find the damn title
		m = TITLE_RE.search(resp.data)
		if not m:
			self.sendReply(trigger, 'Page parsing failed: area.')
			return
		
		title = m.group(1)
		
		# Find the damn area in the title
		area = None
		for r in TITLE_REs:
			m = r.match(title)
			if m:
				area = m.group(1)
				break
		
		if area is None:
			self.sendReply(trigger, 'Page parsing failed: area.')
			return
		
		# Find the Giant Table
		chunk = FindChunk(resp.data, 'Last updated:', '</table>')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: data.')
			return
		
		# Remove any 'empty' rows
		chunk = chunk.replace('<tr></tr>', '')
		
		# Find the rows in it
		chunks = FindChunks(chunk, '<tr>', '</tr>')
		if not chunks:
			self.sendReply(trigger, 'Page parsing failed: data.')
			return
		
		# Wander through the chunks parsing them
		parts = []
		tz = None
		
		for tr in chunks:
			# Skip non-useful ones
			if tr.find('<td nowrap') < 0:
				# Might be useful for time/date
				if tz is None:
					m = re.search('Date Time<br>\((.+)\)</th>', tr)
					if m:
						tz = m.group(1)
				
				continue
			
			# Split the row into lines
			lines = StripHTML(tr)
			
			# Work out where we are, removing evil chars
			place = lines[0]
			
			# Strip some crap
			for crap in (' &times;', ' *'):
				place = place.replace(crap, '')
			
			# If we're just updating location data, do that
			if location is None:
				self.__Locations.setdefault(area, []).append(place)
			
			# If we're looking for some info, do that
			elif place.lower() == location.lower():
				try:
					updated = lines[1].split()[1]
					temp = lines[2]
					humidity = float(lines[4])
					wind_dir = lines[5]
					wind_speed = lines[6]
				
				except (IndexError, ValueError):
					parts.append('no current data found!')
				
				else:
					if tz:
						part = '\02[\02%s %s\02]\02' % (updated, tz)
					else:
						part = '\02[\02Updated: %s\02]\02' % (updated)
					parts.append(part)
					
					part = '\02[\02Temp: %s°C\02]\02' % (temp)
					parts.append(part)
					
					part = '\02[\02Humidity: %.1f%%\02]\02' % (humidity)
					parts.append(part)
					
					# Wind is a bit messy
					if wind_dir == '-' and wind_speed == '-':
						wind_info = 'no data'
					elif wind_dir == 'CALM':
						wind_info = 'Calm'
					else:
						wind_info = '%s %skm/h' % (wind_dir, wind_speed)
					
					part = '\02[\02Wind: %s\02]\02' % (wind_info)
					parts.append(part)
				
				break
		
		# If we're updating, finish that up	
		if location is None:
			trigger.count += 1
			
			# If we've finished updating, party
			if trigger.count == len(PRODUCTS):
				self.putlog(LOG_ALWAYS, 'AusBOM: Finished updating location data.')
				
				self.__Locations['_updated_'] = time.time()
				self.savePickle('.ausbom.locations', self.__Locations)
				
				self.__updating = 0
			
			# Otherwise, go get the next one
			else:
				url = AUSBOM_URL % PRODUCTS[trigger.count][1]
				self.urlRequest(trigger, self.__Parse_Current, url)
		
		# If we're not updating, maybe spit out something
		else:
			if parts == []:
				replytext = 'no data found!'
			else:
				replytext = '%s :: %s' % (place, ' '.join(parts))
			
			self.sendReply(trigger, replytext, process=0)
	
	# -----------------------------------------------------------------------
	# Find the right 'product' for a location
	def __Find_Product(self, trigger, location):
		exacts = []
		partials = {}
		
		for area, product, priority in PRODUCTS:
			if area not in self.__Locations:
				tolog = 'AusBOM: %s not in area data?!' % area
				self.putlog(LOG_WARNING, tolog)
				continue
			
			# Exact match, don't need dodgy matching
			if location in self.__Locations[area]:
				exact = (priority, product)
				exacts.append(exact)
				continue
			
			# Look for other matches
			else:
				lowloc = location.lower()
				
				# Wrong case
				blurf = [l for l in self.__Locations[area] if l.lower() == lowloc]
				if blurf:
					exact = (priority, product)
					exacts.append(exact)
					continue
				
				# Partial matches
				for l in self.__Locations[area]:
					if l.lower().find(lowloc) >= 0:
						partials[l] = 1
		
		# If we had any exact matches, return the highest priority one
		if exacts:
			exacts.sort()
			return exacts[0][1]
		
		# If we had any partials, maybe spit those out
		elif partials:
			# We only want the first 10
			pks = partials.keys()
			pks.sort()
			partials = pks[:10]
			
			parts = []
			
			part = "No exact matches, \02%d\02 partial(s) for '%s' ::" % (len(partials), location)
			parts.append(part)
			
			for partial in partials:
				part = '\02[\02%s\02]\02' % partial
				parts.append(part)
			
			# Spit it out
			replytext = ' '.join(parts)
		
		# None at all? Bah!
		else:
			replytext = "No matching locations found for '%s'" % (location)
		
		# Send reply!
		self.sendReply(trigger, replytext)
		
		return None

# ---------------------------------------------------------------------------
