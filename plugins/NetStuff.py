# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Miscellaneous commands for various network things.'

import os
import re
import socket

from classes.async_buffered import buffered_dispatcher

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------
# Some hosts are stupid
WHOIS_HOSTS = {
	'com': 'whois.crsnic.net',
	'net': 'whois.crsnic.net',
	'org': 'whois.publicinterestregistry.net',
}

# Various line formats we've run in to. Fuck WHOIS servers and their inability
# to use a standard reply format :|
WHOIS_LINES = {
	'created': (
		'Created On',
		'Domain Registration Date',
		'Creation Date',
		'Domain registered',
		'Registered on',
	),
	'updated': (
		'Last Updated On',
		'Domain Last Updated Date',
		'Updated Date',
		'Last Modified',
		'changed',
		'Last updated',
	),
	'expires': (
		'Expiration Date',
		'Domain Expiration Date',
		'Record will expire on',
		'Renewal Date',
	),
	'status': (
		'Status',
		'Domain Status',
		'status',
	),
}

# ---------------------------------------------------------------------------

class NetStuff(Plugin):
	_HelpSection = 'net'
	
	def setup(self):
		# Load our collection of ccTLDs
		self.__ccTLDs = {}
		
		filename = os.path.join('data', 'cctlds')
		try:
			cctld_file = open(filename, 'r')
		except IOError:
			self.putlog(LOG_WARNING, "Can't find data/cctlds!")
		else:
			for line in cctld_file:
				line = line.strip()
				if not line:
					continue
				
				cctld, country = line.split(None, 1)
				self.__ccTLDs[cctld] = country
			
			cctld_file.close()
		
		# See if we have services info
		self.__Ports = {}
		if os.access('/etc/services', os.R_OK):
			for line in open('/etc/services', 'r'):
				line = line.strip()
				if not line or line.startswith('#') or not '/' in line:
					continue
				
				parts = line.split()
				if len(parts) < 2:
					continue
				
				self.__Ports[parts[0].lower()] = parts[1].split('/')[0]
	
	# ---------------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__ccTLD,
			regexp = re.compile('^cctld (.+)$'),
			help = ('cctld', '\02cctld\02 <code> OR <country> : Look up the country for <code>, or search for the ccTLD for <country>.'),
		)
		self.addTextEvent(
			method = self.__Resolve_DNS,
			regexp = re.compile('^dns (?P<host>.+)$'),
			help = ('dns', '\02dns02 <hostname> : Try to resolve hostname to IP(s).'),
		)
		self.addTextEvent(
			method = self.__Port,
			regexp = re.compile('^port (.{1,20})$'),
			help = ('port', '\02port\02 <port> OR <name> : Look up the service name for a port, or the port for a service name.'),
		)
		self.addTextEvent(
			method = self.__Resolve_WHOIS,
			regexp = re.compile('^whois (?P<domain>[A-Za-z0-9-\.]+)$'),
			help = ('whois', '\02whois\02 <domain> : Look up <domain> in the WHOIS database.'),
		)
	
	# ---------------------------------------------------------------------------
	# Someone wants to look up a ccTLD!
	def __ccTLD(self, trigger):
		findme = trigger.match.group(1).lower()
		
		# Evil people should die
		if len(findme) <= 1:
			self.sendReply(trigger, "That's too short!")
			return
		if len(findme) > 20:
			self.sendReply(trigger, "That's too long!")
			return
		
		# Two letters should be a country code
		if len(findme) == 2:
			findme = '.%s' % findme
		
		# Country code time
		if len(findme) == 3 and findme.startswith('.'):
			if findme in self.__ccTLDs:
				replytext = '%s is the ccTLD for %s' % (findme, self.__ccTLDs[findme])
			else:
				replytext = 'No such ccTLD: %s' % findme
		
		# Country name
		else:
			matches = [c for c in self.__ccTLDs.items() if c[1].lower().find(findme) >= 0]
			if matches:
				if len(matches) == 1:
					replytext = '%s is the ccTLD for %s' % (matches[0][0], matches[0][1])
				else:
					parts = []
					for cctld, country in matches:
						part = '\02[\02%s: %s\02]\02' % (cctld, country)
						parts.append(part)
					replytext = ' '.join(parts)
			else:
				replytext = "No matches found for '%s'" % (findme)
		
		# Spit something out
		self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	def __Port(self, trigger):
		if self.__Ports == {}:
			self.sendReply(trigger, "No ports known, missing /etc/services?")
			return
		
		findme = trigger.match.group(1).lower()
		
		# Port number search
		if findme.isdigit():
			if 0 < int(findme) < 65536:
				matches = [k for k, v in self.__Ports.items() if v == findme]
				if matches:
					replytext = "Port %s is service '%s'" % (findme, matches[0])
				else:
					replytext = "No match found."
			else:
				replytext = "Invalid port specified."
		# Service name search
		else:
			if findme in self.__Ports:
				replytext = "Service '%s' is port %s" % (findme, self.__Ports[findme])
			else:
				# No exact match, be yucky
				matches = [k for k in self.__Ports.keys() if findme in k]
				if matches:
					replytext = "No exact match, partial matches :: %s" % (', '.join(matches[:20]))
				else:
					replytext = "No exact or partial matches found."
		
		self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	
	def __Resolve_DNS(self, trigger):
		host = trigger.match.group('host').lower().strip()
		if not host:
			self.sendReply(trigger, 'Empty host?')
		elif len(host) < 4:
			self.sendReply(trigger, "That's too short!")
		elif '.' not in host:
			self.sendReply(trigger, "That's not a hostname!")
		else:
			self.dnsLookup(trigger, self.__Reply_DNS, host)
	
	def __Reply_DNS(self, trigger, hosts, args):
		host = trigger.match.group('host').lower().strip()
		
		if not hosts:
			replytext = "Could not resolve '%s'!" % (host)
		else:
			ips = [h[1] for h in hosts[:10]]
			if len(hosts) > 10:
				replytext = "\x02%s\x02 result(s), first \x0210\x02 - [%s]"
			else:
				replytext = "\x02%s\x02 result(s) - [%s]"
			replytext = replytext % (len(hosts), ', '.join(ips))
		
		self.sendReply(trigger, replytext)
	
	# ---------------------------------------------------------------------------
	# Someone wants to WHOIS a domain! Resolve the whois server.
	def __Resolve_WHOIS(self, trigger):
		domain = trigger.match.group('domain').lower()
		parts = domain.split('.')
		if not (2 <= len(parts) <= 3 and 2 <= len(parts[-1]) <= 4):
			self.sendReply(trigger, "That doesn't look like a domain!")
			return
		
		wsn = '%s.whois-servers.net' % (parts[-1])
		host = WHOIS_HOSTS.get(parts[-1], wsn)
		
		self.dnsLookup(trigger, self.__Fetch_WHOIS, host, domain, parts)
	
	# Go fetch the data we need!
	def __Fetch_WHOIS(self, trigger, hosts, args):
		domain, parts = args
		
		# We only want IPv4 hosts.
		if not hosts:
			wsn = '%s.whois-servers.net' % (parts[-1])
			host = WHOIS_HOSTS.get(parts[-1], wsn)
			
			replytext = "Unable to resolve '%s' - invalid TLD?" % (host)
			self.sendReply(trigger, replytext)
			
			return
		
		# Spawn the WHOIS client
		hosts = [h for h in hosts if h[0] == 4]
		async_whois(self, trigger, domain, hosts[0][1])
	
	# Parse the result!
	def _Parse_WHOIS(self, trigger, domain, lines):
		# Beep, fail
		if not lines:
			replytext = "No WHOIS data for '%s' found." % (domain)
			self.sendReply(trigger, replytext)
			return
		
		# Off we go
		updated = created = expires = status = None
		
		for line in lines:
			line = line.strip()
			#print '>', repr(line)
			if not line or ':' not in line:
				continue
			
			if not created and [i for i in WHOIS_LINES['created'] if line.startswith(i)]:
				created = line.split(':', 1)[1].strip()
			elif not updated and [i for i in WHOIS_LINES['updated'] if line.startswith(i)]:
				updated = line.split(':', 1)[1].strip()
			elif not expires and [i for i in WHOIS_LINES['expires'] if line.startswith(i)]:
				expires = line.split(':', 1)[1].strip()
			elif not status and [i for i in WHOIS_LINES['status'] if line.startswith(i)]:
				status = line.split(':', 1)[1].strip()
			
		
		# See if we got some data
		parts = []
		
		if status:
			part = '\x02[\x02Status: %s\x02]\x02' % (status)
			parts.append(part)
		if created:
			part = '\x02[\x02Created: %s\x02]\x02' % (created)
			parts.append(part)
		if updated:
			part = '\x02[\x02Updated: %s\x02]\x02' % (updated)
			parts.append(part)
		if expires:
			part = '\x02[\x02Expires: %s\x02]\x02' % (expires)
			parts.append(part)
		
		# And spit something out
		if parts:
			replytext = "WHOIS data for '%s': %s" % (domain, ' '.join(parts))
		else:
			replytext = "No WHOIS data, or unable to parse result for '%s'." % (domain)
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------

class async_whois(buffered_dispatcher):
	def __init__(self, parent, trigger, domain, host):
		buffered_dispatcher.__init__(self)
		
		self.data = []
		self.status = 0
		
		self.parent = parent
		self.trigger = trigger
		self.domain = domain
		
		# Create the socket
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		
		# Try to connect.
		try:
			self.connect((host, 43))
		except socket.gaierror, msg:
			tolog = "Error while trying to WHOIS: %s" % (msg)
			self.parent.putlog(LOG_WARNING, tolog)
			self.close()
	
	def handle_connect(self):
		# Nasty hack for stupid german server
		if self.domain.endswith('.de'):
			tosend = '-T dn,ace -C US-ASCII %s\r\n' % (self.domain)
		else:
			tosend = '%s\r\n' % self.domain
		
		self.send(tosend)
	
	def handle_read(self):
		data = self.recv(4096)
		#print repr(data)
		self.data.append(data)
	
	def handle_close(self):
		lines = ''.join(self.data).splitlines()
		self.parent._Parse_WHOIS(self.trigger, self.domain, lines)
		
		self.close()

# ---------------------------------------------------------------------------
