#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

import cPickle
import os
import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

MONEY_CURRENCY = 'MONEY_CURRENCY'
CURRENCY_RE = re.compile('^currency (?P<curr>\w+)$')
CURRENCY_HELP = "'\02currency\02 <code OR partial name>' : Look up the currency code and name, given the specified information"

MONEY_EXCHANGE = 'MONEY_EXCHANGE'
EXCHANGE_RE = re.compile('^exchange (?P<amt>[\d\.]+) (?P<from>\w\w\w)(?: to | )(?P<to>\w\w\w)$')
EXCHANGE_HELP = "'\02exchange\02 <amount> <currency 1> \02to\02 <currency 2>' : Convert currency using current exchange rates. Currencies are specified using their three letter code."
EXCHANGE_URL = 'http://finance.yahoo.com/m5?a=%(amt)s&s=%(from)s&t=%(to)s&c=0'

MONEY_QUOTE = 'MONEY_QUOTE'
QUOTE_RE = re.compile('^quote (?P<symbol>\S+)$')
QUOTE_HELP = '\02quote\02 <symbol> : Look up a current stock price.'
QUOTE_URL = 'http://finance.yahoo.com/q?d=v1&s=%s'

MONEY_SYMBOL = 'MONEY_SYMBOL'
SYMBOL_RE = re.compile('^symbol (?P<findme>.+)$')
SYMBOL_HELP = '\02symbol\02 <findme> : Look up a ticker symbol.'
SYMBOL_URL = 'http://finance.yahoo.com/l?t=S&m=&s=%s'

# ---------------------------------------------------------------------------

class MoneyMangler(Plugin):
	"""
	Convert money from one currency to another.
	"""
	
	def setup(self):
		config_dir = self.Config.get('plugin', 'config_dir')
		config_file = os.path.join(config_dir, 'currency.data')
		try:
			f = file(config_file, 'rb')
		except:
			tolog = "couldn't open %s, MoneyMangler plugin will not work as intended!" % config_file
			self.putlog(LOG_WARNING, tolog)
		else:
			try:
				self.Currencies = cPickle.load(f)
			except:
				self.Currencies = {}
				tolog = "error loading data from %s, MoneyMangler plugin will not work as intended!" % config_fie
				self.putlog(LOG_WARNING, tolog)
			else:
				f.close()
				tolog = 'loaded %d currencies from %s' % (len(self.Currencies), config_file)
				self.putlog(LOG_DEBUG, tolog)
	
	def rehash(self):
		self.setup()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		self.setTextEvent(MONEY_CURRENCY, CURRENCY_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(MONEY_EXCHANGE, EXCHANGE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(MONEY_QUOTE, QUOTE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.setTextEvent(MONEY_SYMBOL, SYMBOL_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('money', 'currency', CURRENCY_HELP)
		self.setHelp('money', 'exchange', EXCHANGE_HELP)
		self.setHelp('money', 'quote', QUOTE_HELP)
		self.setHelp('money', 'symbol', SYMBOL_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone wants to look for a currency
		if trigger.name == MONEY_CURRENCY:
			self.__Search(trigger)
		
		# Someone wants to do a money conversion
		elif trigger.name == MONEY_EXCHANGE:
			replytext = None
			
			data = {}
			data['amt'] = '%.2f' % float(trigger.match.group('amt'))
			data['from'] = trigger.match.group('from').upper()
			data['to'] = trigger.match.group('to').upper()
			
			if data['from'] not in self.Currencies:
				replytext = '%(from)s is not a valid currency code' % data
			elif data['to'] not in self.Currencies:
				replytext = '%(to)s is not a valid currency code' % data
			elif 'e' in data['amt']:
				replytext = '%(amt)s is beyond the range of convertable values' % data
			else:
				url = EXCHANGE_URL % data
				returnme = (trigger, data)
				self.urlRequest(returnme, url)
			
			if replytext is not None:
				self.sendReply(trigger, replytext)
		
		# Someone wants to look up a stock price
		elif trigger.name == MONEY_QUOTE:
			symbol = trigger.match.group('symbol').upper()
			returnme = (trigger, symbol)
			fetchme = QUOTE_URL % symbol
			self.urlRequest(returnme, fetchme)
		
		# Someone wants to look up a ticker symbol
		elif trigger.name == MONEY_SYMBOL:
			findme = trigger.match.group('findme').upper()
			returnme = (trigger, findme)
			fetchme = SYMBOL_URL % findme
			self.urlRequest(returnme, fetchme)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_URL(self, message):
		(trigger, data), page_text = message.data
		
		# Money has been exchanged
		if trigger.name == MONEY_EXCHANGE:
			self.__Exchange(trigger, page_text, data)
		
		# Stock quote has returned
		elif trigger.name == MONEY_QUOTE:
			self.__Quote(trigger, page_text, data)
		
		# The symbol is known
		elif trigger.name == MONEY_SYMBOL:
			self.__Symbol(trigger, page_text, data)
	
	# -----------------------------------------------------------------------
	# Parse the exchange page and spit out a result
	def __Exchange(self, trigger, page_text, data):
		page_text = page_text.replace('&amp;', ' and ')
		
		# Find the table chunk
		chunk = FindChunk(page_text, '<table border=1', '</table>')
		
		# Put each tag on a new line
		chunk = chunk.replace('>', '>\n')
		
		# Split it into lines
		lines = StripHTML(chunk)
		
		# If it's the right data, we have a winner
		if lines[0] == 'Symbol' and lines[2] == 'Exchange Rate':
			replytext = '%s %s == %s %s' % (lines[8], data['from'], lines[11], data['to'])
		# If it's not, we failed miserably
		else:
			replytext = 'Page parsing failed.'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Find a matching currency!
	def __Currency(self, trigger):
		curr = trigger.match.group('curr').lower()
		
		# Possible currency code?
		if len(curr) == 3:
			ucurr = curr.upper()
			if ucurr in self.Currencies:
				replytext = '%s (%s)' % (self.Currencies[ucurr], ucurr)
				self.sendReply(trigger, replytext)
				return
		
		# Search the whole bloody lot
		found = []
		for code, name in self.Currencies.items():
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
	# Parse the stock quote page and spit out a result
	def __Quote(self, trigger, page_text, data):
		# Invalid symbol, sorry
		if page_text.find('is not a valid ticker symbol') >= 0:
			replytext = '"%s" is not a valid ticker symbol!' % data
		
		else:
			# Find the data we need
			chunk = FindChunk(page_text, '<table class="yfnc_datamodoutline1"', '</table>')
			if chunk is None:
				self.putlog(LOG_WARNING, 'Stock page parsing failed: no stock data')
				self.sendReply(trigger, 'Failed to parse page properly')
				return
			
			# Replace the up/down graphics with +/-
			chunk = re.sub(r'alt="Down">\s*', '>-', chunk)
			chunk = re.sub(r'alt="Up">\s*', '>+', chunk)
			
			# Strip the evil HTML!
			lines = StripHTML(chunk)
			
			# Sort out the stock info
			info = {'Symbol': data}
			for line in lines:
				parts = re.split(r'\s*:\s*', line, 1)
				if len(parts) == 2 and parts[1] != 'N/A':
					if parts[0] in ('Last Trade', 'Index Value'):
						info['Value'] = parts[1]
					else:
						info[parts[0]] = parts[1]
			
			# Output something now :)
			if info:
				try:
					replytext = '[%(Trade Time)s] %(Symbol)s: %(Value)s %(Change)s' % info
				except KeyError:
					replytext = 'Some stock data missing, not good!'
			else:
				replytext = 'No stock data found? WTF?'
		
		self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Parse the stock symbol page and spit out a result
	def __Symbol(self, trigger, page_text, data):
		# No matches, sorry
		if page_text.find('returned no Stocks matches') >= 0:
			replytext = 'No symbols found matching "%s"' % data
			self.sendReply(trigger, replytext)
		
		else:
			# Find the chunk of data we need
			chunk = FindChunk(page_text, 'Add to My Portfolio', 'View Quotes for All Above Symbols')
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

# ---------------------------------------------------------------------------
