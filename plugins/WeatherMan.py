# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Checks the weather!

import re
from urllib import quote

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

WEATHER_WEATHER = 'WEATHER_WEATHER'

WEATHER_RE = re.compile('^weather\s+(?P<location>.+)$')
WEATHER_HELP = '\02weather\02 <location> : Retrieve weather information for location'
WEATHER_URL = "http://search.weather.yahoo.com/search/weather2?p=%s"

s1 = '[%(location)s] %(weather)s, Currently: %(currently_c)s°C (%(currently_f)s°F)'
s2 = ', High: %(hi_c)s°C (%(hi_f)s°F), Low: %(lo_c)s°C (%(lo_f)s°F)'
s3 = ', Wind: %(wind)s, Feels Like: %(like_c)s°C (%(like_f)s°F)'
s4 = ', Humidity: %(humidity)s, Visibility: %(visibility)s'
s5 = ', Sunrise: %(sunrise)s, Sunset: %(sunset)s'
WEATHER_REPLY = s1 + s2 + s3 + s4 + s5

# ---------------------------------------------------------------------------

class WeatherMan(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		weather_dir = PluginTextEvent(WEATHER_WEATHER, IRCT_PUBLIC_D, WEATHER_RE)
		weather_msg = PluginTextEvent(WEATHER_WEATHER, IRCT_MSG, WEATHER_RE)
		self.register(weather_dir, weather_msg)
		
		self.setHelp('weather', 'weather', WEATHER_HELP)
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == WEATHER_WEATHER:
			url = WEATHER_URL % quote(trigger.match.group('location'))
			self.urlRequest(trigger, url)
	
	def _message_REPLY_URL(self, message):
		trigger, page_text = message.data
		
		if trigger.name == WEATHER_WEATHER:
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
				chunks = []
				
				
				# Find the chunk that tells us where we are
				m = re.search(r'<\!--BROWSE: ADD BREADCRUMBS-->(.*?)<script', page_text, re.M | re.S)
				if not m:
					self.putlog(LOG_WARNING, 'Weather page parsing failed: no location data')
					self.sendReply(trigger, 'Failed to parse page properly')
					return
				
				lines = StripHTML(m.group(1))
				
				# Extract location!
				loc1 = lines[-1]
				loc2 = lines[-2][:-2]
				location = '[%s, %s]' % (loc1, loc2)
				
				
				# Find the chunk with the weather data we need
				m = re.search(r'<\!--CURCON-->(.*?)<\!--END CURCON-->', page_text, re.M | re.S)
				if not m:
					self.putlog(LOG_WARNING, 'Weather page parsing failed: no current data')
					self.sendReply(trigger, 'Failed to parse page properly')
					return
				
				# Split into lines that aren't empty
				lines = StripHTML(m.group(1))
				
				# Extract current conditions!
				for line in lines:
					if line.startswith('Currently:'):
						continue
					elif re.match(r'^\d+$', line):
						chunk = 'Currently: %s' % (CandF(line))
						chunks.append(chunk)
					elif line.startswith('Hi:'):
						chunk = 'High: %s' % (CandF(line[3:]))
						chunks.append(chunk)
					elif line.startswith('Lo:'):
						chunk = 'Low: %s' % (CandF(line[3:]))
						chunks.append(chunk)
					else:
						chunks.insert(0, line)
				
				
				# Find some more weather data
				m = re.search(r'<\!--MORE CC-->(.*?)<\!--ENDMORE CC-->', page_text, re.M | re.S)
				if m:
					#self.putlog(LOG_WARNING, 'Weather page parsing failed: no extra data')
					#self.sendReply(trigger, 'Failed to parse page properly')
					#return
					
					# Split into lines that aren't empty
					lines = StripHTML(m.group(1))
					
					# Extract!
					chunk = 'Feels Like: %s' % (CandF(lines[2]))
					chunks.append(chunk)
					
					windbits = lines[-9].split()
					if len(windbits) == 3:
						chunk = 'Wind: %s %s kph (%s mph)' % (windbits[0], ToKilometers(windbits[1]), windbits[1])
					else:
						chunk = windbits[0]
					chunks.append(chunk)
					
					chunk = 'Humidity: %s' % (lines[-7])
					chunks.append(chunk)
					chunk = 'Visibility: %s' % (lines[-3])
					chunks.append(chunk)
					chunk = 'Sunrise: %s' % (lines[-5])
					chunks.append(chunk)
					chunk = 'Sunset: %s' % (lines[-1])
					chunks.append(chunk)
				
				
				#if broken:
				#	self.sendReply(trigger, "Failed to parse page properly")
				
				#else:
				
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
