#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

import cPickle
import os
import re
from HTMLParser import HTMLParser

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
		curr_dir = PluginTextEvent(MONEY_CURRENCY, IRCT_PUBLIC_D, CURRENCY_RE)
		curr_msg = PluginTextEvent(MONEY_CURRENCY, IRCT_MSG, CURRENCY_RE)
		conv_dir = PluginTextEvent(MONEY_EXCHANGE, IRCT_PUBLIC_D, EXCHANGE_RE)
		conv_msg = PluginTextEvent(MONEY_EXCHANGE, IRCT_MSG, EXCHANGE_RE)
		quote_dir = PluginTextEvent(MONEY_QUOTE, IRCT_PUBLIC_D, QUOTE_RE)
		quote_msg = PluginTextEvent(MONEY_QUOTE, IRCT_MSG, QUOTE_RE)
		
		self.register(conv_dir, conv_msg, curr_dir, curr_msg, quote_dir, quote_msg)
		
		self.setHelp('money', 'currency', CURRENCY_HELP)
		self.setHelp('money', 'exchange', EXCHANGE_HELP)
		self.setHelp('money', 'quote', QUOTE_HELP)
		
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone wants to look for a currency
		if trigger.name == MONEY_CURRENCY:
			self.__Currency_Search(trigger)
		
		# Someone wants to do a money conversion
		elif trigger.name == MONEY_EXCHANGE:
			self.__Currency_Exchange(trigger)
		
		# Someone wants to look up a stock price
		elif trigger.name == MONEY_QUOTE:
			self.__Stock_Quote(trigger)
	
	# -----------------------------------------------------------------------
	
	def _message_REPLY_URL(self, message):
		(trigger, data), page_text = message.data
		
		if trigger.name == MONEY_EXCHANGE:
			page_text = page_text.replace('&amp;', ' and ')
			
			parser = YahooParser()
			
			try:
				parser.feed(page_text)
				parser.close()
			except:
				replytext = "Error parsing the html"
				self.sendReply(trigger, replytext)
			else:
				#currencies = {}
				#for curr in parser.currs:
				#	name = curr[:-6]
				#	code = curr[-4:-1]
				#	currencies[code] = name
				#cPickle.dump(currencies, open('configs/currency.data', 'wb'), 1)
				
				if parser.result:
					replytext = '%s %s == %s %s' % (data['amt'], data['from'], parser.result, data['to'])
				else:
					replytext = 'No result returned.'
				self.sendReply(trigger, replytext)
		
		elif trigger.name == MONEY_QUOTE:
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
	
	def __Currency_Exchange(self, trigger):
		data = {}
		data['amt'] = '%.2f' % float(trigger.match.group('amt'))
		data['from'] = trigger.match.group('from').upper()
		data['to'] = trigger.match.group('to').upper()
		
		if data['from'] not in self.Currencies:
			replytext = '%(from)s is not a valid currency code' % data
			self.sendReply(trigger, replytext)
		elif data['to'] not in self.Currencies:
			replytext = '%(to)s is not a valid currency code' % data
			self.sendReply(trigger, replytext)
		elif 'e' in data['amt']:
			replytext = '%(amt)s is beyond the range of convertable values' % data
			self.sendReply(trigger, replytext)
		else:
			fetchme = EXCHANGE_URL % data
			returnme = (trigger, data)
			self.urlRequest(returnme, fetchme)
	
	def __Currency_Search(self, trigger):
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
	
	def __Stock_Quote(self, trigger):
		symbol = trigger.match.group('symbol').upper()
		returnme = (trigger, symbol)
		fetchme = QUOTE_URL % symbol
		self.urlRequest(returnme, fetchme)

# ---------------------------------------------------------------------------
# A parser for the Yahoo Finance currency conversion page
class YahooParser(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		
		#self.__in_select = 0
		#self.__in_option = 0
		#self.currs = []
		
		self.__in_th = 0
		self.__now = 0
		self.result = ''
	
	def handle_starttag(self, tag, attrs):
		#if tag == 'select' and attrs[0][1] == 's':
		#	self.__in_select = 1
		#if tag == 'option' and self.__in_select:
		#	self.__in_option = 1
		
		if tag == 'th':
			self.__in_th = 1
	
	def handle_endtag(self, tag):
		#if tag == 'select':
		#	self.__in_select = 0
		#if tag == 'option' and self.__in_select:
		#	self.__in_option = 0
		
		if tag == 'th':
			self.__in_th = 0
	
	def handle_data(self, data):
		#if self.__in_select and self.__in_option:
		#	self.currs.append(data)
		
		if self.__in_th:
			if data == 'Historical Charts':
				self.__now = 2
		
		elif self.__now:
			self.__now -= 1
			
			if self.__now == 0:
				self.result = data
