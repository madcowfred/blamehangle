# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Plugin to parse the Australian Bureau of Meteorology current observations.

import cPickle
import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

PRODUCTS = (
	# NSW
	('Sydney', 'IDN65066'),
	# QLD
	('Brisbane', 'IDQ65113'),
	('North Queensland', 'IDQ60600'),
	('Western Queensland', 'IDQ60601'),
	('Central Queensland', 'IDQ60602'),
	('Southeast Queensland', 'IDQ60603'),
	# SA
	('Adelaide', 'IDS65012'),
	# TAS
	('Hobart', 'IDT65012'),
	# VIC
	('Melbourne', 'IDV60034'),
	# WA
	('Perth', 'IDW60034'),
)

TITLE_RE = re.compile('<title>(.*?)</title>', re.I)

TITLE_REs = (
	re.compile('^Current (.+) Observations.*$'),
	re.compile('^Current Observations for (.+) Forecast Districts$'),
)

MONTH = 60 * 60 * 24 * 30

# ---------------------------------------------------------------------------

AUSBOM_AUSBOM = 'AUSBOM_AUSBOM'
AUSBOM_HELP = '\02ausbom\02 <location> : Get current weather data for <location>.'
AUSBOM_RE = re.compile('^ausbom (?P<location>.+)$')
AUSBOM_URL = 'http://www.bom.gov.au/products/%s.shtml'

AUSBOM_PUBLIC = 'AUSBOM_PUBLIC'
AUSBOM_UPDATE = 'AUSBOM_UPDATE'

# ---------------------------------------------------------------------------

class AusBOM(Plugin):
	def setup(self):
		# Load our location data from the pickle.
		self.__Locations = self.__Unpickle('ausbom.data')
		# If there isn't any, trigger an update.
 		if self.__Locations is None:
			self.__Update_Locations()
		# If there is, and it's more than a month old, update
		elif time.time() - self.__Locations['_updated_'] > MONTH:
			self.__Update_Locations()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		# Register our normal stuff first
		ausbom_dir = PluginTextEvent(AUSBOM_AUSBOM, IRCT_PUBLIC_D, AUSBOM_RE)
		ausbom_msg = PluginTextEvent(AUSBOM_AUSBOM, IRCT_MSG, AUSBOM_RE)
		self.register(ausbom_dir, ausbom_msg)
		
		self.setHelp('weather', 'ausbom', AUSBOM_HELP)
		self.registerHelp()
		
		# Now register our public commands
		events = []
		pubs = [o for o in self.Config.options('AusBOM') if o.startswith('public.')]
		for pub in pubs:
			# Make the event
			r = re.compile('^%s$' % pub[7:])
			trigname = '%s.%s' % (AUSBOM_PUBLIC, pub[7:])
			event = PluginTextEvent(trigname, IRCT_PUBLIC, r)
			# Stick the location on it so we know what to look for
			event.location = self.Config.get('AusBOM', pub)
			
			events.append(event)
		
		# If we have any more events, register them
		if events:
			self.register(*events)
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == AUSBOM_AUSBOM:
			product = self.__Find_Product(trigger, trigger.match.group('location'))
			if product:
				url = AUSBOM_URL % (product)
				self.urlRequest(trigger, url)
		
		elif trigger.name.startswith(AUSBOM_PUBLIC):
			product = self.__Find_Product(trigger, trigger.event.location)
			if product:
				url = AUSBOM_URL % (product)
				self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == AUSBOM_UPDATE:
			self.__Parse_Current(trigger, page_text)
		
		elif trigger.name == AUSBOM_AUSBOM:
			self.__Parse_Current(trigger, page_text, trigger.match.group('location'))
		
		elif trigger.name.startswith(AUSBOM_PUBLIC):
			self.__Parse_Current(trigger, page_text, trigger.event.location)
	
	# -----------------------------------------------------------------------
	# Send URL requests for updating
	def __Update_Locations(self):
		self.putlog(LOG_ALWAYS, 'AusBOM: Updating location data...')
		
		# Reset the location data
		self.__Locations = {}
		
		# We need a fake trigger here for urlRequest()
		trigger = PluginFakeTrigger(AUSBOM_UPDATE)
		trigger.count = 0
		
		# Go to get the first one
		url = AUSBOM_URL % PRODUCTS[0][1]
		self.urlRequest(trigger, url)
	
	# -----------------------------------------------------------------------
	# Find the right 'product' for a location
	def __Find_Product(self, trigger, location):
		partials = []
		
		for area, product in PRODUCTS:
			if area not in self.__Locations:
				tolog = 'AusBOM: %s not in area data?!' % area
				self.putlog(LOG_WARNING, tolog)
				continue
			
			# Exact match, we're done
			if location in self.__Locations[area]:
				return product
			# Look for other matches
			else:
				lowloc = location.lower()
				
				# Wrong case
				blurf = [l for l in self.__Locations[area] if l.lower() == lowloc]
				if blurf:
					return product
				
				# Partial matches
				blurf = [l for l in self.__Locations[area] if l.lower().find(lowloc) >= 0]
				if blurf:
					partials.extend(blurf)
		
		# If we had any partials, maybe spit those out
		if partials:
			# We only want the first 10
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
		
		return None
	
	# -----------------------------------------------------------------------
	# Parse a Current Observations page. If location is specified we find the
	# data for that location, otherwise we find a list of locations.
	def __Parse_Current(self, trigger, page_text, location=None):
		# Find the damn title
		m = TITLE_RE.search(page_text)
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
		
		# Find the data the easy way, hopefully
		chunks = FindChunks(page_text, '<!-- DATA, ', ' -->')
		if chunks:
			# Location update
			if location is None:
				for chunk in chunks:
					newloc = chunk.split(',')[1].strip()
					self.__Locations.setdefault(area, []).append(newloc)
				
				trigger.count += 1
				
				# If we've finished updating, party
				if trigger.count == len(PRODUCTS):
					self.putlog(LOG_ALWAYS, 'AusBOM: Finished updating location data.')
					
					self.__Locations['_updated_'] = time.time()
					self.__Pickle('ausbom.data', self.__Locations)
				
				# Otherwise, go get the next one
				else:
					url = AUSBOM_URL % PRODUCTS[trigger.count][1]
					self.urlRequest(trigger, url)
			
			# Someone wants some weather
			else:
				# Split it into bits
				parts = []
				
				for chunk in chunks:
					# [	date:time, place, temp, dewpoint, humidity, wind dir, wind speed km/h, wind gust km/h, pressure?
					bits = [a.strip() for a in chunk.split(',')]
					
					go = 0
					
					# Me!
					if bits[1].lower() == location.lower():
						part = '\02[\02Temp: %s°C\02]\02' % (bits[2])
						parts.append(part)
						
						part = '\02[\02Humidity: %.1f%%\02]\02' % (float(bits[4]))
						parts.append(part)
						
						part = '\02[\02Wind: %s %skm/h\02]\02' % (bits[5], bits[6])
						parts.append(part)
						
						#part = '\02[\02Pressure: %s hPa\02]\02' % (bits[7])
						#parts.append(part)
						
						break
				
				if parts == []:
					parts.append('Nothing!')
				
				replytext = '%s :: %s' % (bits[1], ' '.join(parts))
				self.sendReply(trigger, replytext, process=0)
		
		# Guess it's the hard way :(
		else:
			# Find the Giant Table
			chunk = FindChunk(page_text, 'END OF STANDARD BUREAU HEADER', '</table>')
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: data.')
				return
			
			# Find the rows in it
			chunks = FindChunks(chunk, '<tr>', '</tr>')
			if not chunks:
				self.sendReply(trigger, 'Page parsing failed: data.')
				return
			
			# Wander through the chunks parsing them
			parts = []
			
			for tr in chunks:
				# Skip non-useful ones
				if tr.find('<td nowrap') < 0:
					continue
				
				# Split the row into lines
				lines = StripHTML(tr)
				
				# Work out where we are
				place = lines[0].replace(' &times;', '')
				
				if location is None:
					self.__Locations.setdefault(area, []).append(place)
				
				elif place.lower() == location.lower():
					try:
						temp = lines[2]
						humidity = float(lines[4])
						wind_dir = lines[5]
						wind_speed = lines[6]
					
					except ValueError:
						parts.append('no current data found!')
					
					else:
						part = '\02[\02Temp: %s°C\02]\02' % (temp)
						parts.append(part)
						
						part = '\02[\02Humidity: %.1f%%\02]\02' % (humidity)
						parts.append(part)
						
						part = '\02[\02Wind: %s %skm/h\02]\02' % (wind_dir, wind_speed)
						parts.append(part)
					
					break
			
			# If we're updating, finish that up	
			if location is None:
				trigger.count += 1
				
				# If we've finished updating, party
				if trigger.count == len(PRODUCTS):
					self.putlog(LOG_ALWAYS, 'AusBOM: Finished updating location data.')
					
					self.__Locations['_updated_'] = time.time()
					self.__Pickle('ausbom.data', self.__Locations)
				
				# Otherwise, go get the next one
				else:
					url = AUSBOM_URL % PRODUCTS[trigger.count][1]
					self.urlRequest(trigger, url)
			
			# If we're not updating, maybe spit out something
			else:
				if parts == []:
					parts.append('no data found!')
				
				replytext = '%s :: %s' % (place, ' '.join(parts))
				self.sendReply(trigger, replytext, process=0)
	
	# -----------------------------------------------------------------------
	# Pickle an object into the given file
	def __Pickle(self, filename, obj):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, "wb")
		except:
			# We couldn't open our file :(
			tolog = "Unable to open %s for writing" % filename
			self.putlog(LOG_WARNING, tolog)
		else:
			tolog = "Saving pickle to %s" % filename
			self.putlog(LOG_DEBUG, tolog)
			# the 1 turns on binary-mode pickling
			cPickle.dump(obj, f, 1)
			f.flush()
			f.close()
	
	# -----------------------------------------------------------------------
	# Unpickle an object from the given file
	def __Unpickle(self, filename):
		config_dir = self.Config.get('plugin', 'config_dir')
		filename = os.path.join(config_dir, filename)
		
		try:
			f = open(filename, "rb")
		except:
			# Couldn't open the pickle file, so don't try to unpickle
			return None
		else:
			# We have a pickle!
			tolog = "Loading pickle from %s" % filename
			self.putlog(LOG_DEBUG, tolog)
			obj = cPickle.load(f)
			f.close()
			return obj

# ---------------------------------------------------------------------------
