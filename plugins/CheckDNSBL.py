# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004, MadCowDisease
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

'Basic plugin to check joining hosts against DNS Block Lists.'

import re

from classes.Constants import *
from classes.Plugin import Plugin
from classes.SimpleCacheDict import SimpleCacheDict

# ---------------------------------------------------------------------------

IPV4_RE = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
IPV6_RE = re.compile(r'^[A-Z\d]{1,4}:[A-Z\d:]+$', re.I)
RFC1918_RE = re.compile(r'^(?:127\.|10\.|192\.168\.|172\.(?:1[6789]|2[0-9]|3[01])\.)')

# ---------------------------------------------------------------------------

class CheckDNSBL(Plugin):
	def setup(self):
		self.HostCache = SimpleCacheDict(300)
		
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('CheckDNSBL', autosplit=True)
		self.Options['actions'] = self.Options['actions'].split()
	
	def register(self):
		if 'dnsbl' in self.Options:
			self.sendMessage('ChatterGizmo', REQ_IRC_EVENTS, ['join'])
		else:
			self.putlog(LOG_WARNING, 'No DNSBLs configured!')
	
	# -----------------------------------------------------------------------
	
	def _message_IRC_EVENT(self, message):
		wrap, name, args = message.data
		
		if name == 'join':
			chan, ui = args
			if ui is None:
				return
			
			info = { 'wrap': wrap, 'chan': chan, 'ui': ui, 'dnsbls': [], 'hosts': [] }
			
			# It's an IPv4 IP, we can do DNS checks now
			if IPV4_RE.match(ui.host):
				self.__DNS_Host(None, ((4, ui.host),), [info])
			# It's an IPv6 IP, we can't do anything at all
			elif IPV6_RE.match(ui.host):
				return
			# It's a hostname, try to resolve it
			else:
				self.dnsLookup(None, self.__DNS_Host, ui.host, info)
	
	# -----------------------------------------------------------------------
	# We got a reply to a hostname lookup.
	def __DNS_Host(self, trigger, hosts, args):
		# Error!
		if hosts is None:
			return
		
		# Strip any non-IPv4 or RFC 1918 hosts
		hosts = [h[1] for h in hosts if h[0] == 4 and not RFC1918_RE.search(h[1])]
		if not hosts:
			return
		
		# Do the checking
		info = args[0]
		
		for host in hosts:
			# Punish them now
			if True in self.HostCache.get(host, {}).values():
				self.__Punish(info)
				return
			
			# Or not
			for name, opts in self.Options['dnsbl'].items():
				if opts[0] == 'f':
					findme = '%s.%s' % (host, opts[1])
				else:
					parts = host.split('.')
					parts.reverse()
					findme = '%s.%s' % ('.'.join(parts), opts[1])
				
				info['dnsbls'].append((host, name, findme))
		
		# And go start the lookups
		self.dnsLookup(None, self.__DNS_DNSBL, info['dnsbls'][0][2], info)
	
	# -----------------------------------------------------------------------
	# We got a reply to a DNSBL lookup.
	def __DNS_DNSBL(self, trigger, hosts, args):
		info = args[0]
		host, name, findme = info['dnsbls'].pop(0)
		
		# Some replies, see if we have to punish
		if hosts:
			for ip in hosts:
				checks = self.Options['dnsbl'][name][2:]
				
				if checks:
					found = 0
					for check in checks:
						if ip == check:
							found = 1
							break
				else:
					found = 1
			
			# Found 'em
			if found:
				cache = self.HostCache.get(host, {})
				cache[name] = True
				self.HostCache[host] = cache
				
				self.__Punish(info)
				return
		
		# No replies, oh well
		else:
			cache = self.HostCache.get(host, {})
			cache[name] = False
			self.HostCache[host] = cache
		
		# If we still have hosts to check, go do that now
		if info['dnsbls']:
			self.dnsLookup(None, self.__DNS_DNSBL, info['dnsbls'][0][2], info)
	
	# -----------------------------------------------------------------------
	
	def __Punish(self, info):
		# If we're not opped, don't do anything at all
		wrap = info['wrap']
		ournick = wrap.conn.getnick()
		
		tolog = '%s on %s is listed in one of my DNSBL lists!' % (info['ui'], info['chan'])
		self.connlog(wrap, LOG_WARNING, tolog)
		
		if not wrap.ircul.user_has_mode(info['chan'], ournick, 'o'):
			return
		
		for action in self.Options['actions']:
			if action == 'ban':
				command = 'MODE %s +b *!*@%s' % (info['chan'], info['ui'].host)
				wrap.sendline(command)
			
			elif action == 'wall':
				target = '@%s' % (info['chan'])
				text = 'WARNING: %s is listed in one of the DNSBLs that I check!' % (info['ui'])
				self.notice(wrap, target, text)
			
			elif action == 'kick':
				text = 'Your host is listed in one of the DNSBLs that I check.'
				command = 'KICK %s %s :%s' % (info['chan'], info['ui'].nick, text)
				wrap.sendline(command)

# ---------------------------------------------------------------------------
