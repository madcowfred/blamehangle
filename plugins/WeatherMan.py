# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Checks the weather!

import re
from urllib import quote

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

from classes import pymetar

# ---------------------------------------------------------------------------

WEATHER_URL = 'http://search.weather.yahoo.com/search/weather2?p=%s'

WEATHER_SHORT = 'WEATHER_SHORT'
SHORT_RE = re.compile('^weather\s+(?P<location>.+)$')
SHORT_HELP = '\02weather\02 <location> : Retrieve weather information for location (short format)'

WEATHER_LONG = 'WEATHER_LONG'
LONG_RE = re.compile('^weatherlong\s+(?P<location>.+)$')
LONG_HELP = '\02weatherlong\02 <location> : Retrieve weather information for location (long format)'

WEATHER_FORECAST = 'WEATHER_FORECAST'
FORECAST_RE = re.compile('^forecast\s+(?P<location>.+)$')
FORECAST_HELP = '\02forecast\02 <location> : Retrieve weather forecast for location'

# ---------------------------------------------------------------------------

METAR_URL = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/%s.TXT'

WEATHER_METAR = 'METAR'
METAR_RE = re.compile('^metar (?P<station>\S+)$')
METAR_HELP = '\02metar\02 <station id> : Retrieve coded METAR weather information.'

WEATHER_METARD = 'METARD'
METARD_RE = re.compile('^metard (?P<station>\S+)$')
METARD_HELP = '\02metard\02 <station id> : Retrieve decoded METAR weather information.'

# ---------------------------------------------------------------------------

TAF_URL = 'http://weather.noaa.gov/pub/data/forecasts/taf/stations/%s.TXT'

WEATHER_TAF = 'TAF'
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
	
	def _message_PLUGIN_REGISTER(self, message):
		short_dir = PluginTextEvent(WEATHER_SHORT, IRCT_PUBLIC_D, SHORT_RE)
		short_msg = PluginTextEvent(WEATHER_SHORT, IRCT_MSG, SHORT_RE)
		long_dir = PluginTextEvent(WEATHER_LONG, IRCT_PUBLIC_D, LONG_RE)
		long_msg = PluginTextEvent(WEATHER_LONG, IRCT_MSG, LONG_RE)
		forecast_dir = PluginTextEvent(WEATHER_FORECAST, IRCT_PUBLIC_D, FORECAST_RE)
		forecast_msg = PluginTextEvent(WEATHER_FORECAST, IRCT_MSG, FORECAST_RE)
		self.register(short_dir, short_msg, long_dir, long_msg, forecast_dir, forecast_msg)
		
		metar_dir = PluginTextEvent(WEATHER_METAR, IRCT_PUBLIC_D, METAR_RE)
		metar_msg = PluginTextEvent(WEATHER_METAR, IRCT_MSG, METAR_RE)
		metard_dir = PluginTextEvent(WEATHER_METARD, IRCT_PUBLIC_D, METARD_RE)
		metard_msg = PluginTextEvent(WEATHER_METARD, IRCT_MSG, METARD_RE)
		self.register(metar_dir, metar_msg, metard_dir, metard_msg)
		
		taf_dir = PluginTextEvent(WEATHER_TAF, IRCT_PUBLIC_D, TAF_RE)
		taf_msg = PluginTextEvent(WEATHER_TAF, IRCT_MSG, TAF_RE)
		self.register(taf_dir, taf_msg)
		
		self.setHelp('weather', 'weather', SHORT_HELP)
		self.setHelp('weather', 'weatherlong', LONG_HELP)
		self.setHelp('weather', 'forecast', FORECAST_HELP)
		self.setHelp('weather', 'metar', METAR_HELP)
		self.setHelp('weather', 'metard', METARD_HELP)
		self.setHelp('weather', 'taf', TAF_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name in (WEATHER_SHORT, WEATHER_LONG, WEATHER_FORECAST):
			url = WEATHER_URL % quote(trigger.match.group('location'))
			self.urlRequest(trigger, url)
		
		elif trigger.name in (WEATHER_METAR, WEATHER_METARD):
			url = METAR_URL % trigger.match.group('station').upper()
			self.urlRequest(trigger, url)
		
		elif trigger.name == WEATHER_TAF:
			url = TAF_URL % trigger.match.group('station').upper()
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name in (WEATHER_SHORT, WEATHER_LONG, WEATHER_FORECAST):
			self.__Parse_Weather(trigger, page_text)
		
		elif trigger.name in (WEATHER_METAR, WEATHER_METARD):
			self.__Parse_METAR(trigger, page_text)
		
		elif trigger.name == WEATHER_TAF:
			self.__Parse_TAF(trigger, page_text)
	
	# -----------------------------------------------------------------------
	
	def __Parse_Weather(self, trigger, page_text):
		# No results
		if page_text.find('No match found') >= 0:
			replytext = "No matches found for '%s'" % trigger.match.group('location')
			self.sendReply(trigger, replytext)
		
		# More than one result... assume the first one is right
		elif page_text.find('location matches') >= 0:
			m = re.search(r'<a href="(/forecast/\S+\.html)">', page_text)
			if m:
				url = 'http://search.weather.yahoo.com' + m.group(1)
				self.urlRequest(trigger, url)
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
			page_text = page_text.replace('°', '')
			
			
			# Find the chunk that tells us where we are
			chunk = FindChunk(page_text, '<!--BROWSE: ADD BREADCRUMBS-->', '<script')
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
			chunk = FindChunk(page_text, '<!--CURCON-->', '<!--END CURCON-->')
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
			chunk = FindChunk(page_text, '<!--MORE CC-->', '<!--ENDMORE CC-->')
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
			chunk = FindChunk(page_text, '<!----------------------- FORECAST ------------------------->', '<!--ENDFC-->')
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
	
	def __Parse_METAR(self, trigger, page_text):
		stationid = trigger.match.group('station').upper()
		
		# No results
		if page_text.find('Not Found') >= 0:
			replytext = "No such station ID '%s'" % stationid
			self.sendReply(trigger, replytext)
		
		# Use pymetar to parse it
		else:
			# Create the un-mangled report?
			report = pymetar.WeatherReport(stationid)
			report.fullreport = page_text
			
			# Parse the report
			report = pymetar.ReportParser(report).ParseReport()

			# Gather data
			chunks = []
			
			# A coded report, for masochists
			if trigger.name == WEATHER_METAR:
				chunk = report.getRawMetarCode()
				chunks.append(chunk)
			
			# A decoded report
			elif trigger.name == WEATHER_METARD:
				# Add updated time
				chunk = 'Updated: %s' % report.getISOTime()
				chunks.insert(0, chunk)
				
				# Weather
				if report.getWeather() is not None:
					chunk = 'Weather: %s' % report.getWeather()
					chunks.append(chunk)
				
				# Sky conditions
				if report.getSkyConditions() is not None:
					chunk = 'Sky: %s' % report.getSkyConditions()
					chunks.append(chunk)
				
				# Temperature
				if report.getTemperatureCelsius() is not None:
					chunk = 'Temperature: %.1fC' % report.getTemperatureCelsius()
					chunks.append(chunk)
				
				# Wind
				if report.getWindSpeed() > 0.0:
					chunk = 'Wind: %s %dkt' % (report.getWindCompass(), report.getWindSpeed())
					if report.windgusts:
						chunk += ' (gusting to %dkt)' % report.windgusts
				else:
					chunk = 'Wind: calm'
				chunks.append(chunk)
				
				# Wind chill
				if report.windchill:
					chunk = 'Windchill: %.1fC' % report.windchill
					chunks.append(chunk)
				
				# Visibility
				if report.getVisibility() is not None:
					chunk = 'Visibility: %s' % report.getVisibility()
					chunks.append(chunk)
				
				# Humidity
				if report.getHumidity() is not None:
					chunk = 'Humidity: %s%%' % report.getHumidity()
					chunks.append(chunk)
				
				# Air pressure
				if report.getPressure() is not None:
					chunk = 'Pressure: %.0f hPa' % report.getPressure()
					chunks.append(chunk)
			
			
			# Spit it out
			if chunks:
				location = '[%s] ' % report.getStationName()
				replytext = location + ', '.join(chunks)
			else:
				replytext = 'Unable to find any weather info.'
			
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	
	def __Parse_TAF(self, trigger, page_text):
		stationid = trigger.match.group('station').upper()
		
		# No results
		if page_text.find('Not Found') >= 0:
			replytext = "No such station ID '%s'" % stationid
			self.sendReply(trigger, replytext)
		
		# Just spit out the data
		else:
			chunks = []
			lines = page_text.splitlines()
			
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
