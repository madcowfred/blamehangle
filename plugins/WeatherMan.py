# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Checks the weather!'

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

METAR_URL = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/%s.TXT'
TAF_URL = 'http://weather.noaa.gov/pub/data/forecasts/taf/stations/%s.TXT'
WEATHER_URL = 'http://search.weather.yahoo.com/search/weather2?p=%s'

# ---------------------------------------------------------------------------

class WeatherMan(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__Short_Parts = self.Config.get('WeatherMan', 'short').split()
		self.__Long_Parts = self.Config.get('WeatherMan', 'long').split()
		
		self.__Formats = {'default': 'both'}
		for option in self.Config.options('WeatherMan'):
			if option.startswith('formats.'):
				if option == 'formats.default':
					self.__Formats['default'] = self.Config.get('WeatherMan', option)
				else:
					parts = option.lower().split('.')
					if len(parts) == 3:
						format = self.Config.get('WeatherMan', option)
						if format in ('both', 'metric', 'imperial'):
							self.__Formats.setdefault(parts[1], {})[parts[2]] = format
						else:
							tolog = 'Mangled option in WeatherMan config: %s' % (option)
							self.putlog(LOG_WARNING, tolog)
					else:
						tolog = 'Mangled option in WeatherMan config: %s' % (option)
						self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	
	def register(self):
		# Yahoo Weather
		self.addTextEvent(
			method = self.__Fetch_Weather_Forecast,
			regexp = re.compile('^forecast\s+(?P<location>.+)$'),
			help = ('weather', 'forecast', '\02forecast\02 <location> : Retrieve weather forecast for location'),
		)
		self.addTextEvent(
			method = self.__Fetch_Weather_Short,
			regexp = re.compile('^weather\s+(?P<location>.+)$'),
			help = ('weather', 'weather', '\02weather\02 <location> : Retrieve weather information for location (short format)'),
		)
		self.addTextEvent(
			method = self.__Fetch_Weather_Long,
			regexp = re.compile('^weatherlong\s+(?P<location>.+)$'),
			help = ('weather', 'weatherlong', '\02weatherlong\02 <location> : Retrieve weather information for location (long format)'),
		)
		# METAR
		self.addTextEvent(
			method = self.__Fetch_METAR,
			regexp = re.compile('^metar (?P<station>\S+)$'),
			help = ('weather', 'metar', '\02metar\02 <station id> : Retrieve coded METAR weather information.'),
		)
		# TAF
		self.addTextEvent(
			method = self.__Fetch_TAF,
			regexp = re.compile('^taf (?P<station>\S+)$'),
			help = ('weather', 'taf', '\02taf\02 <station id> : Retrieve coded TAF weather forecast.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants some weather information
	def __Fetch_Weather_Forecast(self, trigger):
		url = WEATHER_URL % QuoteURL(trigger.match.group('location'))
		self.urlRequest(trigger, self.__Parse_Weather, url)
	
	def __Fetch_Weather_Long(self, trigger):
		url = WEATHER_URL % QuoteURL(trigger.match.group('location'))
		self.urlRequest(trigger, self.__Parse_Weather, url)
	
	def __Fetch_Weather_Short(self, trigger):
		url = WEATHER_URL % QuoteURL(trigger.match.group('location'))
		self.urlRequest(trigger, self.__Parse_Weather, url)
	
	# -----------------------------------------------------------------------
	# Someone wants METAR data
	def __Fetch_METAR(self, trigger):
		url = METAR_URL % trigger.match.group('station').upper()
		self.urlRequest(trigger, self.__Parse_METAR, url)
	
	# -----------------------------------------------------------------------
	# Someone wants TAF data, the nutter
	def __Fetch_TAF(self, trigger):
		url = TAF_URL % trigger.match.group('station').upper()
		self.urlRequest(trigger, self.__Parse_TAF, url)
	
	# -----------------------------------------------------------------------
	# Parse a Yahoo Weather page
	def __Parse_Weather(self, trigger, resp):
		# No results
		if resp.data.find('No match found') >= 0:
			replytext = "No matches found for '%s'" % trigger.match.group('location')
			self.sendReply(trigger, replytext)
		
		# No useful results
		elif resp.data.find('Browse for a Location') >= 0:
			replytext = "No useful matches found for '%s'" % trigger.match.group('location')
			self.sendReply(trigger, replytext)
		
		# More than one result... assume the first one is right
		elif resp.data.find('location matches') >= 0:
			m = re.search(r'<a href="(/forecast/\S+\.html)">', resp.data)
			if m:
				url = 'http://search.weather.yahoo.com' + m.group(1)
				self.urlRequest(trigger, self.__Parse_Weather, url)
			else:
				tolog = "Weather page parsing failed for '%s'!" % trigger.match.group('location')
				self.putlog(LOG_WARNING, tolog)
				
				replytext = "Page parsing failed for '%s'!" % trigger.match.group('location')
				self.sendReply(trigger, replytext)
		
		# Only one result, hopefully?
		else:
			location = None
			data = {}
			
			# Eat the degree symbols
			resp.data = resp.data.replace('&deg;', '').replace('&ordm;', '').replace('°', '')
			
			
			# Find the chunk that tells us where we are
			chunk = FindChunk(resp.data, '<!--BROWSE: ADD BREADCRUMBS-->', '</b></font>')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Weather page parsing failed: no location data')
				self.sendReply(trigger, 'Failed to parse page properly')
				return
			lines = StripHTML(chunk)
			
			# Extract location!
			loc1 = lines[-1]
			loc2 = lines[-2][:-2]
			location = '[%s, %s]' % (loc1, loc2)
			
			
			# Find the chunk with the weather data we need
			chunk = FindChunk(resp.data, '<!--CURCON-->', '<!--END CURCON-->')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Weather page parsing failed: no current data')
				self.sendReply(trigger, 'Failed to parse page properly')
				return
			lines = StripHTML(chunk)
			
			# Extract current conditions!
			for line in lines:
				if line.startswith('Currently:'):
					continue
				elif re.match(r'^\d+$', line):
					chunk = 'Currently: %s' % (self.GetTemp(trigger, line))
					data['current'] = chunk
				elif line.startswith('High:'):
					chunk = 'High: %s' % (self.GetTemp(trigger, line[5:]))
					data['high'] = chunk
				elif line.startswith('Low:'):
					chunk = 'Low: %s' % (self.GetTemp(trigger, line[4:]))
					data['low'] = chunk
				else:
					data['conditions'] = line
			
			
			# Maybe find some more weather data
			chunk = FindChunk(resp.data, '<!--MORE CC-->', '<!--ENDMORE CC-->')
			if chunk is not None:
				lines = StripHTML(chunk)
				
				# Extract!
				chunk = 'Feels Like: %s' % (self.GetTemp(trigger, lines[2]))
				data['feels'] = chunk
				
				windbits = lines[-9].split()
				if len(windbits) == 3:
					chunk = 'Wind: %s %s' % (windbits[0], self.GetWind(trigger, windbits[1]))
				else:
					chunk = 'Wind: %s' % (windbits[0])
				data['wind'] = chunk
				
				chunk = 'Humidity: %s' % (lines[-7])
				data['humidity'] = chunk
				chunk = 'Visibility: %s' % (lines[-3])
				data['visibility'] = chunk
				chunk = 'Sunrise: %s' % (lines[-5])
				data['sunrise'] = chunk
				chunk = 'Sunset: %s' % (lines[-1])
				data['sunset'] = chunk
			
			
			# Maybe find the forecast
			chunk = FindChunk(resp.data, '<!----------------------- FORECAST ------------------------->', '<!--ENDFC-->')
			if chunk is not None:
				data['forecast'] = None
				lines = StripHTML(chunk)
				
				# If we have enough lines, extract
				if len(lines) >= 32:
					fcs = []
					
					for i in range(5):
						day = lines[i]
						conditions = lines[i+7]
						high = lines[11+(i*2)]
						low = lines[21+(i*2)]
						
						if not (high.isdigit() and low.isdigit()):
							continue
						
						forecast = '\x02[\x02%s: %s, High: %s, Low: %s\x02]\x02' % (day, conditions, self.GetTemp(trigger, high), self.GetTemp(trigger, low))
						fcs.append(forecast)
					
					if fcs:
						data['forecast'] = ' '.join(fcs)
			
			# Build our reply
			chunks = []
			
			if trigger.name == '__Fetch_Weather_Short':
				for part in self.__Short_Parts:
					if data.has_key(part):
						chunks.append(data[part])
			
			elif trigger.name == '__Fetch_Weather_Long':
				for part in self.__Long_Parts:
					if data.has_key(part):
						chunks.append(data[part])
			
			elif trigger.name == '__Fetch_Weather_Forecast':
				# If we got no forecast data, cry here
				if data['forecast'] is None:
					self.sendReply(trigger, "Didn't find any forecast information!")
					return
				chunks.append(data['forecast'])
			
			# And spit it out
			if chunks == []:
				self.sendReply(trigger, "Weather format is broken.")
			else:
				replytext = '%s %s' % (location, ', '.join(chunks))
				self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse a semi-decoded METAR file
	def __Parse_METAR(self, trigger, resp):
		stationid = trigger.match.group('station').upper()
		
		# No results
		if resp.data.find('Not Found') >= 0:
			replytext = "No such station ID '%s'" % stationid
			self.sendReply(trigger, replytext)
		
		# Ok, off we go
		else:
			lines = resp.data.splitlines()
			
			# Get the location
			i = lines[0].find(' (')
			if i >= 0:
				location = lines[0][:i]
			else:
				location = 'Unknown location'
			
			# Find the encoded data
			obs = [l for l in resp.data.splitlines() if l.startswith('ob: ')]
			if obs:
				replytext = '[%s] %s' % (location, obs[0][4:])
			else:
				replytext = 'Unable to find observation data.'
			
			# Spit it out
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse scary TAF info
	def __Parse_TAF(self, trigger, resp):
		stationid = trigger.match.group('station').upper()
		
		# No results
		if resp.data.find('Not Found') >= 0:
			replytext = "No such station ID '%s'" % stationid
			self.sendReply(trigger, replytext)
		
		# Just spit out the data
		else:
			chunks = []
			lines = resp.data.splitlines()
			
			for line in lines[1:]:
				line = line.strip()
				if line:
					chunks.append(line)
			
			if chunks:
				replytext = ' / '.join(chunks)
			else:
				replytext = 'No data found for %s.' % stationid
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def GetTemp(self, trigger, f_val):
		f_val = f_val.strip()
		c_val = ToCelsius(f_val)
		
		if trigger.target is not None:
			network = trigger.conn.options['name'].lower()
			chan = trigger.target.lower()
			format = self.__Formats.get(network, {}).get(chan, self.__Formats['default'])
		else:
			format = self.__Formats['default']
		
		if format == 'both':
			return '%sC (%sF)' % (c_val, f_val)
		elif format == 'metric':
			return '%sC' % (c_val)
		elif format == 'imperial':
			return '%sF' % (f_val)
		else:
			raise ValueError, '%s is an invalid format' % format
	
	def GetWind(self, trigger, mph_val):
		mph_val = mph_val.strip()
		kph_val = ToKilometers(mph_val)
		
		if trigger.target is not None:
			network = trigger.conn.options['name'].lower()
			chan = trigger.target.lower()
			format = self.__Formats.get(network, {}).get(chan, self.__Formats['default'])
		else:
			format = self.__Formats['default']
		
		if format == 'both':
			return '%s kph (%s mph)' % (kph_val, mph_val)
		elif format == 'metric':
			return '%s kph' % (kph_val)
		elif format == 'imperial':
			return '%s mph' % (mph_val)
		else:
			raise ValueError, '%s is an invalid format' % format

# ---------------------------------------------------------------------------

def ToCelsius(val):
	try:
		return '%d' % round((int(val) - 32) * 5.0 / 9)
	except ValueError:
		return '0'

def ToKilometers(val):
	try:
		return '%d' % round(int(val) * 1.60934)
	except ValueError:
		return '0'

# ---------------------------------------------------------------------------
