# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Asks AnimeNFO.com for information about anime.

import asyncore
import re
import socket

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

ANIMENFO = 'ANIMENFO'
ANIMENFO_HELP = '\02animenfo\02 <name> : Retrieve info about anime.'
ANIMENFO_RE = re.compile(r'^animenfo (?P<findme>.+)$')

ANIMENFO_HOST = 'misha.project-on.net'
ANIMENFO_PORT = 3000
ANIMENFO_SEND = '<ANIME><TITLE>%s</TITLE><FIELD>TITLE CATEGORY TOTAL GENRE YEAR STUDIO USDISTRO RATING LINK</FIELD></ANIME>'

# ---------------------------------------------------------------------------

FIELDMAP = {
	'TITLE': 'Title',
	'CATEGORY': 'Category',
	'TOTAL': 'Total',
	'GENRE': 'Genre',
	'YEAR': 'Year',
	'STUDIO': 'Studio',
	'USDISTRO': 'US Distribution',
	'RATING': 'Rating',
	'LINK': 'Link',
}

# ---------------------------------------------------------------------------

class AnimeNFO(Plugin):
	def _message_PLUGIN_REGISTER(self, message):
		animenfo_dir = PluginTextEvent(ANIMENFO, IRCT_PUBLIC_D, ANIMENFO_RE)
		animenfo_msg = PluginTextEvent(ANIMENFO, IRCT_MSG, ANIMENFO_RE)
		self.register(animenfo_dir, animenfo_msg)
		
		self.setHelp('animenfo', 'animenfo', ANIMENFO_HELP)
		self.registerHelp()
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == ANIMENFO:
			async_animenfo(self, trigger)
	
	def Parse_Result(self, trigger, data):
		data = data.replace('\n', '').strip()
		if data:
			m = re.match('^<OUTPUT>(.+)</OUTPUT>$', data, re.S)
			if m:
				# Split into field,value pairs
				fields = re.findall(r'<(.+)>(.+)</\1>', m.group(1))
				
				field, value = fields[0]
				
				if field == 'ERROR':
					replytext = 'AnimeNFO returned error %s' % value
				
				elif field == 'RESULT':
					if value == '0':
						replytext = 'No matches found.'
					
					elif value == '1':
						chunks = []
						for field, value in fields[1:]:
							chunk = '[%s] %s' % (FIELDMAP[field], value)
							chunks.append(chunk)
						
						replytext = ' - '.join(chunks)
					
					else:
						items = ['"%s"' % v for f, v in fields[1:]]
						items.sort()
						
						replytext = 'Found \02%d\02 results: ' % (len(items))
						replytext += ', '.join(items)
				
				else:
					replytext = 'Unable to parse AnimeNFO output.'
			
			else:
				replytext = 'Unable to parse AnimeNFO output.'
		
		else:
			replytext = 'No data returned.'
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------

class async_animenfo(asyncore.dispatcher_with_send):
	def __init__(self, parent, trigger):
		asyncore.dispatcher_with_send.__init__(self)
		
		self.data = ''
		self.status = 0
		
		self.parent = parent
		self.trigger = trigger
		
		# Create the socket
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		
		# Try to connect. It seems this will blow up if it can't resolve the
		# host.
		try:
			self.connect((ANIMENFO_HOST, ANIMENFO_PORT))
		except socket.gaierror, msg:
			tolog = "Error while trying to visit AnimeNFO: %s - %s" % (self.url, msg)
			self.parent.putlog(LOG_ALWAYS, tolog)
			self.close()
	
	def handle_connect(self):
		pass
	
	def handle_read(self):
		data = self.recv(2048)
		
		# Welcome message
		if self.status == 0:
			self.status = 1
			tosend = ANIMENFO_SEND % self.trigger.match.group('findme')
			self.send(tosend)
		
		# Data!
		else:
			self.data += data
	
	def handle_close(self):
		self.parent.Parse_Result(self.trigger, self.data)
		
		self.close()

# ---------------------------------------------------------------------------
