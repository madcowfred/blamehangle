# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Checks the weather!'

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

WEATHER_URL = 'http://search.weather.yahoo.com/search/weather2?p=%s'

WEATHER_SHORT = 'WEATHER_SHORT'
SHORT_HELP = '\02weather\02 <location> : Retrieve weather information for location (short format)'
SHORT_RE = re.compile('^weather\s+(?P<location>.+)$')

WEATHER_LONG = 'WEATHER_LONG'
LONG_HELP = '\02weatherlong\02 <location> : Retrieve weather information for location (long format)'
LONG_RE = re.compile('^weatherlong\s+(?P<location>.+)$')

WEATHER_FORECAST = 'WEATHER_FORECAST'
FORECAST_HELP = '\02forecast\02 <location> : Retrieve weather forecast for location'
FORECAST_RE = re.compile('^forecast\s+(?P<location>.+)$')

# ---------------------------------------------------------------------------

METAR_URL = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/%s.TXT'

WEATHER_METAR = 'WEATHER_METAR'
METAR_RE = re.compile('^metar (?P<station>\S+)$')
METAR_HELP = '\02metar\02 <station id> : Retrieve coded METAR weather information.'

# ---------------------------------------------------------------------------

TAF_URL = 'http://weather.noaa.gov/pub/data/forecasts/taf/stations/%s.TXT'

WEATHER_TAF = 'WEATHER_TAF'
TAF_RE = re.compile('^taf (?P<station>\S+)$')
TAF_HELP = '\02taf\02 <station id> : Retrieve coded TAF weather forecast.'

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
		self.setTextEvent(WEATHER_FORECAST, FORECAST_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WEATHER_LONG, LONG_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(WEATHER_SHORT, SHORT_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# METAR
		self.setTextEvent(WEATHER_METAR, METAR_RE, IRCT_PUBLIC_D, IRCT_MSG)
		# TAF
		self.setTextEvent(WEATHER_TAF, TAF_RE, IRCT_PUBLIC_D, IRCT_MSG)
		
		self.registerEvents()
		
		self.setHelp('weather', 'weather', SHORT_HELP)
		self.setHelp('weather', 'weatherlong', LONG_HELP)
		self.setHelp('weather', 'forecast', FORECAST_HELP)
		self.setHelp('weather', 'metar', METAR_HELP)
		self.setHelp('weather', 'taf', TAF_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	# Someone wants some weather information
	def _trigger_WEATHER_SHORT(self, trigger):
		url = WEATHER_URL % quote(trigger.match.group('location'))
		self.urlRequest(trigger, self.__Parse_Weather, url)
	
	_trigger_WEATHER_LONG = _trigger_WEATHER_SHORT
	_trigger_WEATHER_FORECAST = _trigger_WEATHER_SHORT
	
	# -----------------------------------------------------------------------
	# Someone wants METAR data
	def _trigger_WEATHER_METAR(self, trigger):
		url = METAR_URL % trigger.match.group('station').upper()
		self.urlRequest(trigger, self.__Parse_METAR, url)
	
	# -----------------------------------------------------------------------
	# Someone wants TAF data, the nutter
	def _trigger_WEATHER_TAF(self, trigger):
		url = TAF_URL % trigger.match.group('station').upper()
		self.urlRequest(trigger, self.__Parse_TAF, url)
	
	# -----------------------------------------------------------------------
	# Parse a Yahoo Weather page
	def __Parse_Weather(self, trigger, resp):
		# No results
		if resp.data.find('No match found') >= 0:
			replytext = "No matches found for '%s'" % trigger.match.group('location')
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
			resp.data = resp.data.replace('&ordm;', '')
			resp.data = resp.data.replace('°', '')
			
			
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
				elif line.startswith('Hi:'):
					chunk = 'High: %s' % (self.GetTemp(trigger, line[3:]))
					data['high'] = chunk
				elif line.startswith('Lo:'):
					chunk = 'Low: %s' % (self.GetTemp(trigger, line[3:]))
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
				lines = StripHTML(chunk)
				
				# Extract!
				fcs = []
				
				for i in range(1, 5):
					day = lines[i]
					
					first = i + (6 - i) + (i * 4)
					conditions = lines[first]
					high = lines[first+2]
					low = lines[first+3][4:]
					
					forecast = '%s: %s, High: %s, Low: %s' % (day, conditions, self.GetTemp(trigger, high), self.GetTemp(trigger, low))
					fcs.append(forecast)
				
				data['forecast'] = ' - '.join(fcs)
			
			
			chunks = []
			
			if trigger.name == WEATHER_SHORT:
				for part in self.__Short_Parts:
					if data.has_key(part):
						chunks.append(data[part])
			
			elif trigger.name == WEATHER_LONG:
				for part in self.__Long_Parts:
					if data.has_key(part):
						chunks.append(data[part])
			
			elif trigger.name == WEATHER_FORECAST:
				chunks.append(data['forecast'])
			
			
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
