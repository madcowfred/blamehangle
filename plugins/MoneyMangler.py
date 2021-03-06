# Copyright (c) 2003-2009, blamehangle team
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

'Commands for playing with money.'

import os
import re
import time

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

ASX_URL = 'http://www.asx.com.au/asx/markets/EquitySearchResults.jsp?method=get&template=F1001&ASXCodes=%s'
CURRENCY_URL = 'http://www.xe.com/ucc/full/'
EXCHANGE_URL = 'http://www.xe.com/ucc/convert.cgi'
QUOTE_URL = 'http://finance.yahoo.com/q?d=v1&s=%s'
SYMBOL_URL = 'http://finance.yahoo.com/l?t=S&m=&s=%s'
USDEBT_URL = 'http://www.brillig.com/debt_clock/'

TITLE_RE = re.compile('<title>(\S+): Summary for (.*?) -')

# ---------------------------------------------------------------------------

class MoneyMangler(Plugin):
	_HelpSection = 'money'
	
	def setup(self):
		self.__Currencies = {}
		
		filename = os.path.join('data', 'currencies')
		
		update = 0
		if os.path.isfile(filename):
			# If the file is a week or more old, update the list
			timediff = time.time() - os.stat(filename).st_mtime
			if timediff > (7 * 24 * 60 * 60):
				update = 1
				self.logger.info('Currency data is stale, updating...')
			# Guess it's current-ish, try loading it
			else:
				self.__Load_Currencies(filename)
				if len(self.__Currencies) == 0:
					update = 1
					self.logger.info('Currency data file is empty, updating...')
		
		else:
			# File isn't even here
			update = 1
			self.logger.info('Currency data is missing, updating...')
		
		# If we have to update, go do that
		if update:
			trigger = PluginFakeTrigger('CURRENCY_UPDATE')
			self.urlRequest(trigger, self.__Update_Currencies, CURRENCY_URL)
	
	# Load our currency data
	def __Load_Currencies(self, filename):
		try:
			curr_file = open(filename, 'r')
		except IOError:
			tolog = 'Unable to open %s, currency conversion is broken!' % filename
			self.logger.warn(tolog)
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
			self.logger.info(tolog)
	
	# -----------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_ASX,
			regexp = r'^asx (?P<symbol>.+)$',
			help = ('asx', '\02asx\02 <symbol> : Look up a current stock price on the ASX.'),
		)
		self.addTextEvent(
			method = self.__Currency,
			regexp = r'^currency (?P<curr>\w+)$',
			help = ('currency', '\02currency\02 <code OR partial name> : Look up an ISO 4217 currency code and name, given the specified information.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Exchange,
			regexp = r'^exchange (?P<amt>[\d\.]+)(?: from | )(?P<from>\w\w\w)(?: to | )(?P<to>\w\w\w)$',
			help = ('exchange', '\02exchange\02 <amount> <currency 1> \02to\02 <currency 2> : Convert currency using current exchange rates. Currencies are specified using their three letter ISO 4217 code.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Quote,
			regexp = r'^quote (?P<symbol>\S+)$',
			help = ('quote', '\02quote\02 <symbol> : Look up a current stock price.'),
		)
		self.addTextEvent(
			method = self.__Fetch_Symbol,
			regexp = r'^symbol (?P<findme>.+)$',
			help = ('symbol', '\02symbol\02 <findme> : Look up a ticker symbol.'),
		)
		self.addTextEvent(
			method = self.__Fetch_USDebt,
			regexp = r'^usdebt$',
			help = ('usdebt', '\02usdebt\02 : Look up the current US National Debt.'),
		)
	
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
	# Someone wants to lookup a stock or stocks on the ASX
	def __Fetch_ASX(self, trigger):
		symbols = trigger.match.group('symbol').upper().split()
		if not symbols:
			self.sendReply(trigger, 'No symbols supplied!')
			return
		
		url = ASX_URL % ('+'.join(symbols))
		self.urlRequest(trigger, self.__Parse_ASX, url)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a money conversion
	def __Fetch_Exchange(self, trigger):
		replytext = None
		
		data = {
			'Amount': '%.2f' % float(trigger.match.group('amt')),
			'From': trigger.match.group('from').upper(),
			'To': trigger.match.group('to').upper(),
		}
		
		if data['From'] not in self.__Currencies:
			replytext = '%(From)s is not a valid currency code' % data
		elif data['To'] not in self.__Currencies:
			replytext = '%(To)s is not a valid currency code' % data
		elif 'e' in data['Amount']:
			replytext = '%(Amount)s is beyond the range of convertable values' % data
		else:
			self.urlRequest(trigger, self.__Parse_Exchange, EXCHANGE_URL, data)
		
		if replytext is not None:
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to look up a stock price
	def __Fetch_Quote(self, trigger):
		symbol = trigger.match.group('symbol').upper()
		url = QUOTE_URL % (symbol)
		self.urlRequest(trigger, self.__Parse_Quote, url)
		
	# -----------------------------------------------------------------------
	# Someone wants to look up a ticker symbol
	def __Fetch_Symbol(self, trigger):
		findme = trigger.match.group('findme').upper()
		url = SYMBOL_URL % (findme)
		self.urlRequest(trigger, self.__Parse_Symbol, url)
	
	# Someone wants to see how far in the hole the US is
	def __Fetch_USDebt(self, trigger):
		self.urlRequest(trigger, self.__Parse_USDebt, USDEBT_URL)
	
	# -----------------------------------------------------------------------
	# Parse the ASX page and spit out any results
	def __Parse_ASX(self, trigger, resp):
		# Get all table rows
		trs = FindChunks(resp.data, '<tr', '</tr>')
		if not trs:
			self.logger.warn('ASX page parsing failed: no table rows?!')
			self.sendReply(trigger, 'Failed to parse page.')
			return
		
		# Parse any that are the ones we're after
		infos = []
		
		for tr in trs:
			if "<th scope='row' class='row'>" not in tr:
				continue
			
			# Find all table cells in this row
			tds = FindChunks(tr, '<td', '</td>')
			if not tds:
				self.logger.warn('ASX page parsing failed: no table cells?!')
				self.sendReply(trigger, 'Failed to parse page.')
				return
			
			# Get our data
			symbol = StripHTML(FindChunk(tr, '<th', '</th>'))[0]
			if symbol.endswith(' *'):
				symbol = symbol[:-2]
			last = StripHTML(tds[0])[0]
			change = StripHTML(tds[1])[0]
			if not change.startswith('-'):
				change = '+' + change
			
			info = '\02[\02%s: %s %s\02]\02' % (symbol, last, change)
			infos.append(info)
		
		# If we have any stocks, spit em out
		if infos:
			replytext = ' '.join(infos)
		else:
			replytext = 'No stock data found.'
		
		self.sendReply(trigger, replytext)
	
	
	# -----------------------------------------------------------------------
	# Parse the exchange page and spit out a result
	def __Parse_Exchange(self, trigger, resp):
		# Find the data chunk
		chunk = FindChunk(resp.data, 'class="CnvrsnTxt"', '</tr>')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed: class.')
			return
		
		# Find the TDs
		chunks = FindChunks(chunk, '<td', '/td>')
		if not chunks:
			self.sendReply(trigger, 'Page parsing failed: tds.')
			return
		
		# And off we go
		if len(chunks) == 3:
			src = FindChunk(chunks[0], '>', '<').split('&nbsp;')
			dst = FindChunk(chunks[2], '>', '<').split('&nbsp;')
			replytext = '%s %s == %s %s' % (src[0], src[1][:3], dst[0], dst[1][:3])
		else:
			replytext = 'Page parsing failed: chunks.'
			self.logger.warn('Page parsing failed: chunks')
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the stock quote page and spit out a result
	def __Parse_Quote(self, trigger, resp):
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
				self.logger.warn('Stock page parsing failed: no stock data')
				self.sendReply(trigger, 'Failed to parse page.')
				return
			
			# Replace the up/down graphics with +/-
			chunk = re.sub(r'alt="Down">\s*', '>-', chunk)
			chunk = re.sub(r'alt="Up">\s*', '>+', chunk)
			
			# Split into table rows
			chunks = FindChunks(chunk, '<tr>', '</tr>')
			if not chunks:
				self.logger.warn('Stock page parsing failed: no stock chunks')
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
	def __Parse_Symbol(self, trigger, resp):
		findme = trigger.match.group('findme').upper()
		
		# No matches, sorry
		if resp.data.find('returned no Stocks matches') >= 0:
			replytext = 'No symbols found matching "%s"' % (findme)
			self.sendReply(trigger, replytext)
		
		else:
			# Find the chunk of data we need
			chunk = FindChunk(resp.data, 'Add to My Portfolio', 'View Quotes for All Above Symbols')
			if chunk is None:
				self.logger.warn('Stock page parsing failed: no stock data')
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
		chunk = FindChunk(resp.data, '<select name="From"', '</select>')
		if not chunk:
			self.logger.warn('Page parsing failed while updating currencies.')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)
			return
		
		# Find the options
		chunks = FindChunks(chunk, '<option ', '/option>')
		if not chunks:
			self.logger.warn('Page parsing failed while updating currencies.')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)
			return
		
		# Parse 'em
		for chunk in chunks:
			code = FindChunk(chunk, 'value="', '"')
			country = FindChunk(chunk, '>', '<')[:-6]
			if code and country:
				self.__Currencies[code] = country
		
		# We's done
		if self.__Currencies:
			tolog = 'Currency update complete, found %d currencies.' % (len(self.__Currencies))
			self.logger.info(tolog)
			
			try:
				curr_file = open(filename, 'w')
			except IOError:
				tolog = 'Unable to open %s for writing!' % filename
				self.logger.warn(tolog)
			else:
				currs = self.__Currencies.items()
				currs.sort()
				for code, country in currs:
					towrite = '%s %s\n' % (code, country)
					curr_file.write(towrite)
				curr_file.close()
		
		else:
			self.logger.warn('Currency update failed, found 0 currencies!')
			if os.path.isfile(filename):
				self.__Load_Currencies(filename)
	
	# -----------------------------------------------------------------------
	# Parse the US National Debt Clock page
	def __Parse_USDebt(self, trigger, resp):
		# Find the info
		chunk = FindChunk(resp.data, 'HEIGHT=41 ALT="', '"')
		if not chunk:
			self.sendReply(trigger, 'Page parsing failed.')
			return
		
		# Spit it out
		replytext = 'Current U.S. National Debt: %s' % (chunk.replace(' ', ''))
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
