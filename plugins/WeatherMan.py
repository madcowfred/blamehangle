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
	_HelpSection = 'weather'
	
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('WeatherMan')
	
	# -----------------------------------------------------------------------
	
	def register(self):
		# Yahoo Weather
		self.addTextEvent(
			method = self.__Fetch_Weather_Forecast,
			regexp = r'^forecast\s+(?P<location>.+)$',
			help = ('forecast', '\02forecast\02 <location> : Retrieve weather forecast for location'),
		)
		self.addTextEvent(
			method = self.__Fetch_Weather_Short,
			regexp = r'^weather\s+(?P<location>.+)$',
			help = ('weather', '\02weather\02 <location> : Retrieve weather information for location (short format)'),
		)
		self.addTextEvent(
			method = self.__Fetch_Weather_Long,
			regexp = r'^weatherlong\s+(?P<location>.+)$',
			help = ('weatherlong', '\02weatherlong\02 <location> : Retrieve weather information for location (long format)'),
		)
		# METAR
		self.addTextEvent(
			method = self.__Fetch_DMETAR,
			regexp = r'^dmetar (?P<station>\S+)$',
			help = ('dmetar', '\02dmetar\02 <station id> : Retrieve decoded METAR weather information.'),
		)
		self.addTextEvent(
			method = self.__Fetch_METAR,
			regexp = r'^metar (?P<station>\S+)$',
			help = ('metar', '\02metar\02 <station id> : Retrieve coded METAR weather information.'),
		)
		# TAF
		self.addTextEvent(
			method = self.__Fetch_TAF,
			regexp = r'^taf (?P<station>\S+)$',
			help = ('taf', '\02taf\02 <station id> : Retrieve coded TAF weather forecast.'),
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
	def __Fetch_DMETAR(self, trigger):
		url = METAR_URL % trigger.match.group('station').upper()
		self.urlRequest(trigger, self.__Parse_METAR, url)
	
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
			resp.data = resp.data.replace('&deg;', '').replace('&ordm;', '').replace('\xb0', '')
			
			
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
			chunk = FindChunk(resp.data, '<!----------------------- FORECAST ------------------------->', '<!-- END FORECAST -->')
			if chunk is not None:
				lines = StripHTML(chunk)
				
				# If we have enough lines, extract
				if len(lines) >= 22:
					fcs = []
					
					for i in range(5):
						day = lines[i+1]
						
						base = 7+(i*3)
						conditions = lines[base]
						high = lines[base+1][6:]
						low = lines[base+2][5:]
						
						if not (high.isdigit() and low.isdigit()):
							continue
						
						forecast = '\x02[\x02%s: %s, High: %s, Low: %s\x02]\x02' % (day, conditions, self.GetTemp(trigger, high), self.GetTemp(trigger, low))
						fcs.append(forecast)
					
					if fcs:
						data['forecast'] = ' '.join(fcs)
			
			# Build our reply
			chunks = []
			
			if trigger.name == '__Fetch_Weather_Short':
				for part in self.Options['short_parts'].split():
					if part in data:
						chunks.append(data[part])
			
			elif trigger.name == '__Fetch_Weather_Long':
				for part in self.Options['long_parts'].split():
					if part in data:
						chunks.append(data[part])
			
			elif trigger.name == '__Fetch_Weather_Forecast':
				# If we got no forecast data, cry here
				if 'forecast' not in data:
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
		# No results
		if resp.data.find('Not Found') >= 0:
			replytext = "No such station ID '%s'" % trigger.match.group('station').upper()
			self.sendReply(trigger, replytext)
			return
		
		data = {}
		lines = resp.data.splitlines()
		
		# Location
		i = lines[0].find(' (')
		if i >= 0:
			data['location'] = lines[0][:i]
		else:
			data['location'] = 'Unknown location'
		
		# Times
		if lines[1].find('UTC') >= 0:
			chunks = lines[1].split(' / ', 1)
			data['time_local'] = chunks[0]
			data['time_utc'] = chunks[1]
		
		# Other data
		for line in lines[2:]:
			if line.find(':') >= 0:
				chunks = [f.strip() for f in line.split(':')]
				
				if chunks[0] == 'Wind':
					parts = chunks[1].split()
					
					if parts[0].startswith('Calm'):
						data['wind'] = 'Calm'
					elif parts[0] == 'Variable':
						data['wind'] = '%s %s' % (parts[0], self.GetWind(trigger, parts[2]))
						if len(parts) > 7 and parts[6] == 'gusting':
							data['wind'] = '%s (gusting to %s)' % (data['wind'], self.GetWind(trigger, parts[9]))
					else:
						data['wind'] = '%s %s' % (parts[2], self.GetWind(trigger, parts[6]))
						if len(parts) > 11 and parts[10] == 'gusting':
							data['wind'] = '%s (gusting to %s)' % (data['wind'], self.GetWind(trigger, parts[12]))
				
				elif chunks[0] == 'Visibility':
					data['visibility'] = chunks[1]
				
				elif chunks[0] == 'Sky conditions':
					data['sky'] = chunks[1]
				
				elif chunks[0] == 'Weather':
					data['weather'] = chunks[1]
				
				elif chunks[0] == 'Temperature':
					parts = chunks[1].split()
					data['temps'] = self.GetTemp(trigger, parts[0])
				
				elif chunks[0] == 'Dew Point':
					parts = chunks[1].split()
					data['dewpoint'] = self.GetTemp(trigger, parts[0])
				
				elif chunks[0] == 'Relative Humidity':
					data['humidity'] = chunks[1]
				
				elif chunks[0] == 'Pressure (altimeter)':
					parts = chunks[1].split()
					data['pressure'] = int(parts[-2][1:])
				
				elif chunks[0] == 'ob':
					data['coded'] = chunks[1]
		
		# Now spit it out
		if trigger.name == '__Fetch_METAR':
			if 'coded' in data:
				replytext = '[%(location)s] %(coded)s' % data
			else:
				replytext = '[%s] No coded data found!' % (data['location'])
		
		elif trigger.name == '__Fetch_DMETAR':
			parts = []
			
			if 'sky' in data:
				parts.append(data['sky'])
			if 'weather' in data:
				parts.append(data['weather'])
			if 'temps' in data:
				part = 'Currently: %s' % (data['temps'])
				parts.append(part)
			if 'dewpoint' in data:
				part = 'Dew Point: %s' % (data['dewpoint'])
				parts.append(part)
			if 'wind' in data:
				part = 'Wind: %s' % (data['wind'])
				parts.append(part)
			if 'humidity' in data:
				part = 'Humidity: %s' % (data['humidity'])
				parts.append(part)
			if 'visibility' in data:
				part = 'Visibility: %s' % (data['visibility'])
				parts.append(part)
			if 'pressure' in data:
				part = 'Pressure: %s hPa' % (data['pressure'])
				parts.append(part)
			
			if parts:
				replytext = '[%s] %s' % (data['location'], ', '.join(parts))
			else:
				replytext = '[%s] No data found!' % (data['location'])
		
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
		f_val = float(f_val.strip())
		c_val = ToCelsius(f_val)
		
		format = self.Options.get_net('format', trigger, trigger.target)
		if format is None:
			format = self.Options['default_format']
		
		if format == 'both':
			return '%.1fC (%.1fF)' % (c_val, f_val)
		elif format == 'metric':
			return '%.1fC' % (c_val)
		elif format == 'imperial':
			return '%.1fF' % (f_val)
		else:
			raise ValueError, '%s is an invalid format' % format
	
	def GetWind(self, trigger, mph_val):
		mph_val = mph_val.strip()
		kph_val = ToKilometers(mph_val)
		
		format = self.Options.get_net('format', trigger, trigger.target)
		if format is None:
			format = self.Options['default_format']
		
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
		return ((val - 32) * 5.0 / 9)
	except ValueError:
		return 0.0

def ToKilometers(val):
	try:
		return '%d' % (float(val) * 1.60934)
	except ValueError:
		return '0'

# ---------------------------------------------------------------------------
