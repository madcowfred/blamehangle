#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

'Commands for playing with money.'

import os
import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

ASX_URL = 'http://www.asx.com.au/asx/markets/EquitySearchResults.jsp?method=get&template=F1001&ASXCodes=%s'
EXCHANGE_URL = 'http://finance.yahoo.com/currency/convert?amt=%(amt)s&from=%(from)s&to=%(to)s&submit=Convert'
QUOTE_URL = 'http://finance.yahoo.com/q?d=v1&s=%s'
SYMBOL_URL = 'http://finance.yahoo.com/l?t=S&m=&s=%s'

TITLE_RE = re.compile('<title>(\S+): Summary for (.*?) -')

# ---------------------------------------------------------------------------

class MoneyMangler(Plugin):
	def setup(self):
		self.__Currencies = {}
		
		filename = os.path.join('data', 'currencies')
		
		update = 0
		if os.path.isfile(filename):
			# If the file is a week or more old, update the list
			timediff = time.time() - os.stat(filename).st_mtime
			if timediff > (7 * 24 * 60 * 60):
				update = 1
				self.putlog(LOG_ALWAYS, 'Currency data is stale, updating...')
			# Guess it's current-ish, try loading it
			else:
				self.__Load_Currencies(filename)
				if len(self.__Currencies) == 0:
					update = 1
					self.putlog(LOG_ALWAYS, 'Currency data file is empty, updating...')
		
		else:
			# File isn't even here
			update = 1
			self.putlog(LOG_ALWAYS, 'Currency data is missing, updating...')
		
		# If we have to update, go do that
		if update:
			data = {
				'amt': '1.00',
				'from': 'USD',
				'to': 'CAD',
			}
			url = EXCHANGE_URL % data
			trigger = PluginFakeTrigger('CURRENCY_UPDATE')
			self.urlRequest(trigger, self.__Update_Currencies, url)
	
	# Load our currency data
	def __Load_Currencies(self, filename):
		try:
			curr_file = open(filename, 'r')
		except IOError:
			tolog = 'Unable to open %s, currency conversion is broken!' % filename
			self.putlog(LOG_WARNING, tolog)
		else:
			for line in curr_file.readlines():
				line = line.strip()
				if not line:
					continue
				
				try:
					code, country = line.split(None, 1)
					self.__Currencies[code] = country
				except ValueError:
					continue
			
			tolog = 'Loaded %d currencies from %s.' % (len(self.__Currencies), filename)
			self.putlog(LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_ASX,
			regexp = re.compile('^asx (?P<symbol>.+)$'),
			help = ('money', 'asx', '\02asx\02 <symbol> : Look up a current stock price on the ASX.'),
		)
		self.addTextEvent(
			method = self.__Currency,
			regexp = re.compile('^currency (?P<curr>\w+)$'),
			help = ('money', 'currency', '\02currency\02 <code OR partial name> : Look up an ISO 4217 currency code and name, given the specified information.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Exchange,
			regexp = re.compile('^exchange (?P<amt>[\d\.]+) (?P<from>\w\w\w)(?: to | )(?P<to>\w\w\w)$'),
			help = ('money', 'exchange', '\02exchange\02 <amount> <currency 1> \02to\02 <currency 2> : Convert currency using current exchange rates. Currencies are specified using their three letter ISO 4217 code.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Quote,
			regexp = re.compile('^quote (?P<symbol>\S+)$'),
			help = ('money', 'quote', '\02quote\02 <symbol> : Look up a current stock price.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Symbol,
			regexp = re.compile('^symbol (?P<findme>.+)$'),
			help = ('money', 'symbol', '\02symbol\02 <findme> : Look up a ticker symbol.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants to lookup a stock or stocks on the ASX
	def __Fetch_ASX(self, trigger):
		symbol = trigger.match.group('symbol').upper()
		url = ASX_URL % symbol
		self.urlRequest(trigger, self.__ASX, url)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a money conversion
	def __Fetch_Exchange(self, trigger):
		replytext = None
		
		data = {}
		data['amt'] = '%.2f' % float(trigger.match.group('amt'))
		data['from'] = trigger.match.group('from').upper()
		data['to'] = trigger.match.group('to').upper()
		
		if data['from'] not in self.__Currencies:
			replytext = '%(from)s is not a valid currency code' % data
		elif data['to'] not in self.__Currencies:
			replytext = '%(to)s is not a valid currency code' % data
		elif 'e' in data['amt']:
			replytext = '%(amt)s is beyond the range of convertable values' % data
		else:
			url = EXCHANGE_URL % data
			trigger.data = data
			self.urlRequest(trigger, self.__Exchange, url)
		
		if replytext is not None:
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up a stock price
	def __Fetch_Quote(self, trigger):
		symbol = trigger.match.group('symbol').upper()
		url = QUOTE_URL % symbol
		self.urlRequest(trigger, self.__Quote, url)
		
	# -----------------------------------------------------------------------
	# Someone wants to look up a ticker symbol
	def __Fetch_Symbol(self, trigger):
		findme = trigger.match.group('findme').upper()
		url = SYMBOL_URL % findme
		self.urlRequest(trigger, self.__Symbol, url)
	
	# -----------------------------------------------------------------------
	# Parse the ASX page and spit out any results
	def __ASX(self, trigger, resp):
		# Get all table rows
		trs = FindChunks(resp.data, '<tr', '</tr>')
		if not trs:
			self.putlog(LOG_WARNING, 'ASX page parsing failed: no table rows?!')
			self.sendReply(trigger, 'Failed to parse page.')
			return
		
		# Parse any that are the ones we're after
		infos = []
		
		for tr in trs:
			if tr.find('<strong>') < 0:
				continue
			
			# Find all table cells in this row
			tds = FindChunks(tr, '<td', '</td>')
			if not tds:
				self.putlog(LOG_WARNING, 'ASX page parsing failed: no table cells?!')
				self.sendReply(trigger, 'Failed to parse page.')
				return
			
			# Get our data
			symbol = StripHTML(tds[0])[0]
			if symbol.endswith(' *'):
				symbol = symbol[:-2]
			last = StripHTML(tds[1])[0]
			change = StripHTML(tds[2])[0]
			if not change.startswith('-'):
				change = '+' + change
			#volume = StripHTML(tds[8])[0]
			
			info = '\02[\02%s: %s %s\02]\02' % (symbol, last, change)
			infos.append(info)
		
		# If we have any stocks, spit em out
		if infos:
			replytext = ' '.join(infos)
		else:
			replytext = 'No stock data found.'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to find a currency
	def __Currency(self, trigger):
		curr = trigger.match.group('curr').lower()
		
		# Possible currency code?
		if len(curr) == 3:
			ucurr = curr.upper()
			if ucurr in self.__Currencies:
				replytext = '%s (%s)' % (self.__Currencies[ucurr], ucurr)
				self.sendReply(trigger, replytext)
				return
		
		# Search the whole bloody lot
		found = []
		for code, name in self.__Currencies.items():
			if name.lower().find(curr) >= 0:
				found.append(code)
		
		replytext = "Currency search for '%s'" % curr
		
		if found:
			if len(found) == 1:
				replytext += ': %s' % found[0]
			else:
				found.sort()
				replytext += ' (\x02%d\x02 matches)' % len(found)
				finds = ', '.join(found)
				replytext += ": %s" % finds
		else:
			replytext += ': No matches found.'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the exchange page and spit out a result
	def __Exchange(self, trigger, resp):
		data = trigger.data
		resp.data = resp.data.replace('&amp;', ' and ')
		
		# Find the data chunks
		chunks = FindChunks(resp.data, '<td class="yfnc_tabledata1">', '</td>')
		if not chunks:
			self.sendReply(trigger, 'Page parsing failed.')
			return
		
		# And off we go
		if len(chunks) == 7:
			replytext = '%s %s == %s %s' % (chunks[1][3:-4], data['from'], chunks[4][3:-4], data['to'])
		else:
			replytext = 'Page parsing failed.'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the stock quote page and spit out a result
	def __Quote(self, trigger, resp):
		symbol = trigger.match.group('symbol').upper()
		
		# Invalid symbol, sorry
		if resp.data.find('is not a valid ticker symbol') >= 0:
			replytext = '"%s" is not a valid ticker symbol!' % symbol
		
		else:
			# See if we can get the title
			m = TITLE_RE.search(resp.data)
			if m:
				showme = '%s (%s)' % (m.group(2), m.group(1))
			else:
				showme = symbol
			
			# Find the data we need
			chunk = FindChunk(resp.data, 'class="yfnc_datamodoutline1"', '</table>')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Stock page parsing failed: no stock data')
				self.sendReply(trigger, 'Failed to parse page.')
				return
			
			# Replace the up/down graphics with +/-
			chunk = re.sub(r'alt="Down">\s*', '>-', chunk)
			chunk = re.sub(r'alt="Up">\s*', '>+', chunk)
			
			# Split into table rows
			chunks = FindChunks(chunk, '<tr>', '</tr>')
			if not chunks:
				self.putlog(LOG_WARNING, 'Stock page parsing failed: no stock chunks')
				self.sendReply(trigger, 'Failed to parse page.')
				return
			
			# Sort out the stock info
			info = {'Showme': showme}
			
			for tr in chunks:
				line = StripHTML(tr)[0]
				parts = re.split(r'\s*:\s*', line, 1)
				if len(parts) == 2 and parts[1] != 'N/A':
					if parts[0] in ('Last Trade', 'Index Value'):
						info['Value'] = parts[1]
					elif parts[0] == 'Change':
						info['Value'] = '%s %s' % (info['Value'], parts[1])
					else:
						info[parts[0]] = parts[1]
			
			# Output something now :)
			if info:
				try:
					replytext = '[%(Trade Time)s] %(Showme)s: %(Value)s' % info
					# Add the chart url
					replytext = '%s - http://ichart.yahoo.com/z?s=%s&t=5d&q=l&l=on&z=l&p=s' % (replytext, symbol.upper())
				except KeyError:
					replytext = 'Some stock data missing, not good!'
			else:
				replytext = 'No stock data found? WTF?'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the stock symbol page and spit out a result
	def __Symbol(self, trigger, resp):
		findme = trigger.match.group('findme').upper()
		
		# No matches, sorry
		if resp.data.find('returned no Stocks matches') >= 0:
			replytext = 'No symbols found matching "%s"' % findme
			self.sendReply(trigger, replytext)
		
		else:
			# Find the chunk of data we need
			chunk = FindChunk(resp.data, 'Add to My Portfolio', 'View Quotes for All Above Symbols')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Stock page parsing failed: no stock data')
				self.sendReply(trigger, 'Page parsing failed.')
				return
			
			# Put each tag on a new line
			chunk = chunk.replace('>', '>\n')
			
			# Split it into lines
			lines = StripHTML(chunk)
			
			# Parse it
			bit = 0
			symbol = ''
			parts = []
			
			for line in lines:
				if bit == 0:
					bit = 1
					symbol = line
				
				elif bit == 1:
					bit = 2
					
					part = '\02[\02%s: %s\02]\02' % (symbol, line)
					parts.append(part)
					
					if len(parts) == 10:
						break
				
				elif bit == 2 and line == 'Add':
					bit = 0
					symbol = ''
			
			# Spit something out
			replytext = ' '.join(parts)
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Update the currency list
	def __Update_Currencies(self, trigger, resp):
		filename = os.path.join('data', 'currencies')
		
		# Find the giant list
		chunk = FindChunk(resp.data, '<input name="amt"', '</select>')
		if not chunk:
			self.putlog(LOG_WARNING, 'Page parsing failed while updating currencies.')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)
			return
		
		# Find the options
		chunks = FindChunks(chunk, '<option ', '</option>')
		if not chunks:
			self.putlog(LOG_WARNING, 'Page parsing failed while updating currencies.')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)
			return
		
		# Parse 'em
		for chunk in chunks:
			vn = chunk.find('value=')
			if vn >= 0:
				code = chunk[vn+7:vn+10]
				country = chunk[vn+12:-6]
				if code and country:
					self.__Currencies[code] = country
		
		# We's done
		if self.__Currencies:
			tolog = 'Currency update complete, found %d currencies.' % (len(self.__Currencies))
			self.putlog(LOG_ALWAYS, tolog)
			
			try:
				curr_file = open(filename, 'w')
			except IOError:
				tolog = 'Unable to open %s for writing!' % filename
				self.putlog(LOG_WARNING, tolog)
			else:
				currs = self.__Currencies.items()
				currs.sort()
				for code, country in currs:
					towrite = '%s %s\n' % (code, country)
					curr_file.write(towrite)
				curr_file.close()
		
		else:
			self.putlog(LOG_WARNING, 'Currency update failed, found 0 currencies!')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)

# ---------------------------------------------------------------------------
