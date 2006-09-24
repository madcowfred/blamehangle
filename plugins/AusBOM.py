# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
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

'Retrieve current weather data from the Australian Bureau of Meteorology.'

import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin, PluginFakeTrigger

# ---------------------------------------------------------------------------
# Tuples of 'products'. Should be (product name, page code).
PRODUCTS = (
	('New South Wales', 'IDN65188'),
	('Northern Territory', 'IDD65149'),
	('Queensland', 'IDQ60606'),
	('South Australia', 'IDS65111'),
	('Tasmania', 'IDT65023'),
	('Victoria', 'IDV65121'),
	('Western Australia', 'IDW65120'),
)

OLD_PRODUCTS = (
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
			regexp = r'^ausbom (?P<location>.+)$',
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
		
		# Find the area
		area = FindChunk(resp.data, '<title>Latest Weather Observations for ', '</title>')
		if area is None:
			self.sendReply(trigger, 'Page parsing failed: area.')
			return
		
		# Find the timezone
		tz = FindChunk(resp.data, 'Station Name</th>', '/acronym>')
		if tz is None:
			self.sendReply(trigger, 'Page parsing failed: timezone.')
			return
		tz = FindChunk(tz, '(Australia)">', '<')
		
		# Find the table rows
		trs = FindChunks(resp.data, '<td class="rowleftcolumn">', '</tr>')
		if not trs:
			self.sendReply(trigger, 'Page parsing failed: rows.')
			return
		
		# Wander through the chunks parsing them
		parts = []
		
		for tr in trs:
			# Place name
			place = FindChunk(tr, 'html">', '</a>')
			for crap in ('*',):
				place = place.replace(crap, '')
			place = place.strip()
			
			tds = FindChunks(tr, '<td', '</td>')
			
			# If we're just updating location data, do that
			if location is None:
				self.__Locations.setdefault(area, []).append((place, place.lower()))
			
			# If we're looking for some info, do that
			elif place.lower() == location.lower() and len(tds) >= 7:
				# updated
				part = '\02[\02%s %s\02]\02' % (tds[0][1:].strip(), tz)
				parts.append(part)
				
				# temperature
				part = '\02[\02Temp: %s\xb0C\02]\02' % (tds[1][1:].strip())
				parts.append(part)
				
				# humidity
				if humidity != '-':
					part = '\02[\02Humidity: %.1f%%\02]\02' % (float(tds[3][1:].strip())
					parts.append(part)
				
				# Wind is a bit messy
				wind_dir = tds[5][1:].strip()
				wind_speed = tds[6][1:].strip()
				if wind_dir != '-' and wind_speed != '-':
					if wind_dir == 'CALM':
						wind_info = 'Calm'
					else:
						wind_info = '%s %skm/h' % (wind_dir, wind_speed)
					
					part = '\02[\02Wind: %s\02]\02' % (wind_info)
					parts.append(part)
		
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
		partials = []
		
		for area, product in PRODUCTS:
			if area not in self.__Locations:
				tolog = 'AusBOM: %s not in area data?!' % area
				self.putlog(LOG_WARNING, tolog)
				continue
			
			# Exact match, don't need dodgy matching
			if location in self.__Locations[area]:
				return product
			
			# Look for other matches
			else:
				lowloc = location.lower()
				
				# Wrong case
				for l, ll in self.__Locations[area]:
					if lowloc == ll:
						return product
				
				# Partial matches
				for l, ll in self.__Locations[area]:
					if lowloc in ll:
						partials.append(l)
		
		# If we had any partials, maybe spit those out
		if partials:
			# We only want the first 10
			partials.sort()
			partials = partials[:10]
			
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

# ---------------------------------------------------------------------------
