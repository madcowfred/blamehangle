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

# ---------------------------------------------------------------------------

WEATHER_URL = "http://search.weather.yahoo.com/search/weather2?p=%s"

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

class WeatherMan(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__Short_Parts = self.Config.get('WeatherMan', 'short').split()
		self.__Long_Parts = self.Config.get('WeatherMan', 'long').split()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		short_dir = PluginTextEvent(WEATHER_SHORT, IRCT_PUBLIC_D, SHORT_RE)
		short_msg = PluginTextEvent(WEATHER_SHORT, IRCT_MSG, SHORT_RE)
		long_dir = PluginTextEvent(WEATHER_LONG, IRCT_PUBLIC_D, LONG_RE)
		long_msg = PluginTextEvent(WEATHER_LONG, IRCT_MSG, LONG_RE)
		forecast_dir = PluginTextEvent(WEATHER_FORECAST, IRCT_PUBLIC_D, FORECAST_RE)
		forecast_msg = PluginTextEvent(WEATHER_FORECAST, IRCT_MSG, FORECAST_RE)
		self.register(short_dir, short_msg, long_dir, long_msg, forecast_dir, forecast_msg)
		
		self.setHelp('weather', 'weather', SHORT_HELP)
		self.setHelp('weather', 'weatherlong', LONG_HELP)
		self.setHelp('weather', 'forecast', FORECAST_HELP)
		
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name in (WEATHER_SHORT, WEATHER_LONG, WEATHER_FORECAST):
			url = WEATHER_URL % quote(trigger.match.group('location'))
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name in (WEATHER_SHORT, WEATHER_LONG, WEATHER_FORECAST):
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
						chunk = 'Currently: %s' % (CandF(line))
						data['current'] = chunk
					elif line.startswith('Hi:'):
						chunk = 'High: %s' % (CandF(line[3:]))
						data['high'] = chunk
					elif line.startswith('Lo:'):
						chunk = 'Low: %s' % (CandF(line[3:]))
						data['low'] = chunk
					else:
						data['conditions'] = line
				
				
				# Maybe find some more weather data
				chunk = FindChunk(page_text, '<!--MORE CC-->', '<!--ENDMORE CC-->')
				if chunk is not None:
					lines = StripHTML(chunk)
					
					# Extract!
					chunk = 'Feels Like: %s' % (CandF(lines[2]))
					data['feels'] = chunk
					
					windbits = lines[-9].split()
					if len(windbits) == 3:
						chunk = 'Wind: %s %s kph (%s mph)' % (windbits[0], ToKilometers(windbits[1]), windbits[1])
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
						
						forecast = '%s: %s, High: %s, Low: %s' % (day, conditions, CandF(high), CandF(low))
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

# ---------------------------------------------------------------------------

def StripHTML(text):
	# Remove all HTML tags
	mangled = re.sub(r'(?s)<.*?>', '', text)
	# Eat escaped bits and pieces
	mangled = re.sub(r'\&.*?\;', '', mangled)
	# Eat annoying degrees!
	mangled = re.sub('°', '', mangled)
	# Split into lines that aren't empty
	lines = [s.strip() for s in mangled.splitlines() if s.strip()]
	# Return!
	return lines

def CandF(f_val):
	return '%s°C (%s°F)' % (ToCelsius(f_val), f_val)

def ToCelsius(val):
	return '%d' % round((int(val) - 32) * 5.0 / 9)

def ToKilometers(val):
	return '%d' % round(int(val) * 1.60934)
