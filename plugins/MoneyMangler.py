#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------

import cPickle
import os
import re
from HTMLParser import HTMLParser

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

MONEY_CONVERT = 'MONEY_CONVERT'
MONEY_CURRENCY = 'MONEY_CURRENCY'

CONVERT_RE = re.compile('^convert (?P<amt>[\d\.]+) (?P<from>\w\w\w)(?: to | )(?P<to>\w\w\w)$')
CURRENCY_RE = re.compile('^currency (?P<curr>\w+)$')

EXCHANGE_URL = 'http://finance.yahoo.com/m5?a=%(amt)s&s=%(from)s&t=%(to)s&c=0'


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
	
	def _message_REQ_REHASH(self, message):
		self.setup()
	
	# -----------------------------------------------------------------------
	
	def _message_PLUGIN_REGISTER(self, message):
		conv_dir = PluginTextEvent(MONEY_CONVERT, IRCT_PUBLIC_D, CONVERT_RE)
		conv_msg = PluginTextEvent(MONEY_CONVERT, IRCT_MSG, CONVERT_RE)
		curr_dir = PluginTextEvent(MONEY_CURRENCY, IRCT_PUBLIC_D, CURRENCY_RE)
		curr_msg = PluginTextEvent(MONEY_CURRENCY, IRCT_MSG, CURRENCY_RE)
		
		self.register(conv_dir, conv_msg, curr_dir, curr_msg)
		self.__set_help_msgs()
	
	def __set_help_msgs(self):
		MONEY_CONVERT_HELP = "'\02convert\02 <amount> <currency 1> \02to\02 <currency 2>' : Convert currency using current exchange rates. Currencies are specified using their three letter code"
		MONEY_CURRENCY_HELP = "'\02currency\02 <code OR partial name>' : Look up the currency code and name, given the specified information"
		
		self.setHelp('money', 'convert', MONEY_CONVERT_HELP)
		self.setHelp('money', 'currency', MONEY_CURRENCY_HELP)
	
	# -----------------------------------------------------------------------

	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		# Someone wants to do a money conversion
		if trigger.name == MONEY_CONVERT:
			self.__Currency_Convert(trigger)
		
		# Someone wants to look for a currency
		elif trigger.name == MONEY_CURRENCY:
			self.__Currency_Search(trigger)
	
	def _message_REPLY_URL(self, message):
		(trigger, data), page_text = message.data
		page_text = page_text.replace('&amp;', ' and ')
		
		if trigger.name == MONEY_CONVERT:
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
	
	# -----------------------------------------------------------------------
	
	def __Currency_Convert(self, trigger):
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
		
		#mmhmeiu
		
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
