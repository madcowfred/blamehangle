# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Main IRC event handler. Slightly terrifying due to multiple server code.
"""

import re
import time

from classes.asyncIRC import asyncIRC
from classes.Children import Child
from classes.Constants import *
from classes.WrapConn import *

# ---------------------------------------------------------------------------
# bold | codes off | reverse | underline | 3 forms of colours
RE_STRIP_CODES = re.compile(r'(\x02|\x0F|\x16|\x1F|\x03\d{1,2},\d{1,2}|\x03\d{1,2}|\x03)')

# regexp to see if people are addressing someone
RE_ADDRESSED = re.compile(r'^(?P<nick>\S+)\s*[:;,>]\s*(?P<text>.+)$')

# ---------------------------------------------------------------------------

# Shiny way to look at an event
class IRCEvent:
	def __init__(self, prefix, userinfo, command, target, arguments):
		self.prefix = prefix
		self.userinfo = userinfo
		self.command = command
		self.target = target
		self.arguments = arguments

# ---------------------------------------------------------------------------

class ChatterGizmo(Child):
	def setup(self):
		self.Conns = {}
		self.stopping = 0
		
		self.__Handlers = {}
		self.__Rejoins = []
		
		self.rehash()
	
	def rehash(self):
		self.use_ipv6 = self.Config.getboolean('DNS', 'use_ipv6')
		self.dns_order = self.Config.get('DNS', 'irc_order').strip().split()
		
		# Set up our public commands, if there are any
		self.__Public_Exact = {}
		self.__Public_Param = {}
		
		for option in self.Config.options('Public'):
			command, rewrite = self.Config.get('Public', option).split(None, 1)
			
			if option.startswith('exact'):
				self.__Public_Exact[command] = rewrite
			elif option.startswith('param'):
				self.__Public_Param[command] = rewrite
		
		# Get a list of our old and new networks
		old_nets = [(k, v.network) for k, v in self.Conns.items()]
		new_nets = [s for s in self.Config.sections() if s.startswith('network.')]
		
		for connid, network in old_nets:
			conn = self.Conns[connid].conn
			
			# Update any maybe changed ones
			if network in new_nets:
				options = self.OptionsDict(network)
				self.Conns[connid].parse_options(options)
			
			# Quit and remove any 'gone' networks
			else:
				self.Conns[connid].requested_quit = 1
				self.Conns[connid].conn.quit('So long, and thanks for all the fish.')
		
		# Connect to any newly added networks
		for section in new_nets:
			if not [network for conn, network in old_nets if network == section]:
				options = self.OptionsDict(section)
				
				# Create the IRC connection
				conn = asyncIRC()
				self.Conns[conn.connid] = WrapConn(self, section, conn, options)
				
				# Register our event handler
				conn.register(self._event_handler)
				
				# And connect
				self.Conns[conn.connid].connect()
	
	def shutdown(self, message):
		quitmsg = 'Shutting down: %s' % message.data
		for wrap in self.Conns.values():
			if wrap.conn.status == STATUS_CONNECTED:
				wrap.conn.quit(quitmsg)
		
		self.stopping = 1
	
	# -----------------------------------------------------------------------
	
	def run_sometimes(self, currtime):
		# Stop if we're all done
		if self.stopping:
			for wrap in self.Conns.values():
				if wrap.conn.status == STATUS_CONNECTED:
					return
			
			self.stopnow = 1
			return
		
		# See if we have to try rejoining any channels
		for rejoin in self.__Rejoins:
			last, connid, connect_id, chan = rejoin
			wrap = self.Conns[connid]
			
			if wrap.conn.status != STATUS_CONNECTED or wrap.connect_id != connect_id:
				self.__Rejoins.remove(rejoin)
				continue
			
			elif (currtime - last) >= 20:
				self.__Rejoins.remove(rejoin)
				self.Conns[connid].join_channel(chan)
		
		# Do other stuff here
		for conn, wrap in self.Conns.items():
			wrap.run_sometimes(currtime)
	
	# -----------------------------------------------------------------------
	# We just got out DNS reply, yay
	def _DNS_Reply(self, trigger, hosts, args):
		connid = args[0]
		self.Conns[connid].really_connect(hosts)
	
	# -----------------------------------------------------------------------
	
	def privmsg(self, connid, nick, text):
		self.Conns[connid].privmsg(nick, text)
	
	def notice(self, connid, nick, text):
		self.Conns[connid].notice(nick, text)
	
	def connlog(self, connid, level, text):
		newtext = '(%s) %s' % (self.Conns[connid].name, text)
		self.putlog(level, newtext)
	
	# -----------------------------------------------------------------------
	# Our handy dandy generic event handler
	def _event_handler(self, connid, prefix, hostmask, command, target, arguments):
		wrap = self.Conns[connid]
		
		# Get our userinfo from the magical list
		if hostmask is not None:
			userinfo = wrap.ircul.get_userinfo(hostmask)
		else:
			userinfo = None
		
		event = IRCEvent(prefix, userinfo, command, target, arguments)
		
		# Trigger any local events
		name = '_handle_%s' % (event.command)
		method = getattr(self, name, None)
		if method is not None:
			method(connid, self.Conns[connid].conn, event)
		
		# Trigger any other events
		#for name, events in self.__Handlers.items():
		#	if event.command in events or 'ALL' in events:
		#		self.sendMessage(name, IRC_EVENT, [self.Conns[connid], event])
	
	# -----------------------------------------------------------------------
	# Raw 376 - End of MOTD (and 422 - No MOTD)
	# -----------------------------------------------------------------------
	def _handle_endofmotd(self, connid, conn, event):
		wrap = self.Conns[connid]
		
		wrap.connect_id += 1
		wrap.conn.status = STATUS_CONNECTED
		
		tolog = 'Connected to %s' % (wrap.server[0])
		self.connlog(connid, LOG_ALWAYS, tolog)
		
		# Set ourselves +i
		wrap.conn.sendline('MODE %s +i' % wrap.conn.getnick())
		
		# Create our mode list
		wrap.ircul._modelist = wrap.conn.features['channel_modes']
		
		# If we're supposed to use NickServ, do so
		if wrap.nickserv_nick and wrap.nickserv_pass:
			tolog = 'Identifying with %s' % (wrap.nickserv_nick)
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			text = 'IDENTIFY %s' % (wrap.nickserv_pass)
			self.privmsg(connid, wrap.nickserv_nick, text)
			
			# Delay our joins by 2 seconds so that we're (probably) identified
			# FIXME: make this not use magic numbers
			badtime = time.time() - 18
			for chan in wrap.channels:
				data = [badtime, wrap.conn.connid, wrap.connect_id, chan]
				self.__Rejoins.append(data)
		
		# Normal joining
		else:
			wrap.join_channels()
	
	_handle_nomotd = _handle_endofmotd
	
	# -----------------------------------------------------------------------
	# We just got disconnected from the server
	# -----------------------------------------------------------------------
	def _handle_disconnect(self, connid, conn, event):
		self.Conns[connid].reset()
		self.Conns[connid].last_connect = time.time()
		
		# Log something useful
		if event is not None and event.arguments is not None:
			tolog = 'Disconnected from server: %s' % (event.arguments[0])
		else:
			tolog = 'Disconnected from server'
		self.connlog(connid, LOG_ALWAYS, tolog)
		
		if not self.stopping:
			if self.Conns[connid].requested_quit:
				tolog = 'Removing network!'
				self.connlog(connid, LOG_ALWAYS, tolog)
				
				del self.Conns[connid]
				del conn
	
	# It was bad.
	def _handle_error(self, connid, conn, event):
		errormsg = event.target
		
		# FIXME - regexp sucks
		m = re.match(r".* \((?P<error>.*?)\)$", errormsg)
		if m:
			errormsg = m.group('error')
		
		tolog = 'ERROR: %s' % (errormsg)
		self.connlog(connid, LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Someone just joined a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_join(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.target.lower()
		nick = event.userinfo.nick
		
		# Us
		if nick == conn.getnick():
			tolog = "Joined %s" % chan
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			# Our userlist needs to know that we joined
			wrap.ircul.user_joined(chan)
			wrap.ircul.user_joined(chan, event.userinfo.hostmask())
			
			# Request the modes set on this channel
			wrap.conn.sendline('MODE %s' % chan)
			
			# Request the list of users on this channel
			wrap.conn.sendline('WHO %s' % chan)
		
		# Not us
		else:
			wrap.ircul.user_joined(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just parted a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_part(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.target.lower()
		nick = event.userinfo.nick
		
		# Us
		if nick == conn.getnick():
			wrap.ircul.user_parted(chan)
			
			tolog = 'Left %s' % chan
			self.connlog(connid, LOG_ALWAYS, tolog)
		
		# Not us
		else:
			wrap.ircul.user_parted(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just quit (including ourselves? not sure)
	# -----------------------------------------------------------------------
	def _handle_quit(self, connid, conn, event):
		wrap = self.Conns[connid]
		nick = event.userinfo.nick
		
		if nick != conn.getnick():
			wrap.ircul.user_quit(nick)
			
			# If it was our primary nickname, try and regain it
			if nick == self.Conns[connid].nicks[0]:
				conn.nick(nick)
	
	# -----------------------------------------------------------------------
	# Someone just changed the mode on a channel we're in
	# -----------------------------------------------------------------------
	def _handle_mode(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.target.lower()
		
		# Parse the mode list
		modes = wrap.conn.parse_modes(event.arguments[0], event.arguments[1:])
		
		# Now do something with them
		for sign, mode, arg in modes:
			# User modes
			if mode in wrap.conn.features['user_modes']:
				if sign == '+':
					wrap.ircul.user_add_mode(chan, arg, mode)
				elif sign == '-':
					wrap.ircul.user_del_mode(chan, arg, mode)
			# Guess it's a channel mode
			else:
				if sign == '+':
					wrap.ircul.chan_add_mode(chan, mode, arg)
				else:
					wrap.ircul.chan_del_mode(chan, mode, arg)
	
	# -----------------------------------------------------------------------
	# Raw 324 - Channel mode is
	# -----------------------------------------------------------------------
	def _handle_channelmodeis(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.arguments[0].lower()
		
		# Parse the mode list
		modes = wrap.conn.parse_modes(event.arguments[1], event.arguments[2:])
		
		# Now do something with them
		for sign, mode, arg in modes:
			if sign == '+':
				wrap.ircul.chan_add_mode(chan, mode, arg)
			else:
				wrap.ircul.chan_del_mode(chan, mode, arg)
	
	# -----------------------------------------------------------------------
	# Someone just invited us to a channel
	# -----------------------------------------------------------------------
	def _handle_invite(self, connid, conn, event):
		chan = event.arguments[0].lower()
		
		if chan in self.Conns[connid].channels:
			tolog = '%s invited me to %s, joining...' % (event.userinfo, chan)
			self.connlog(connid, LOG_ALWAYS, tolog)
			self.Conns[connid].join_channel(chan)
		else:
			tolog = '%s invited me to %s, which is NOT in my channel list!' % (event.userinfo, chan)
			self.connlog(connid, LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Someone was just kicked from a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_kick(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.target.lower()
		kicked = event.arguments[0]
		
		if kicked == conn.getnick():
			tolog = '%s kicked me from %s, rejoining...' % (event.userinfo, chan)
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			wrap.ircul.user_parted(chan)
			wrap.join_channel(chan)
		
		else:
			wrap.ircul.user_parted(chan, kicked)
	
	# -----------------------------------------------------------------------
	# Someone just changed their name (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_nick(self, connid, conn, event):
		wrap = self.Conns[connid]
		before = event.userinfo.nick
		after = event.target
		
		# Update the userlist
		wrap.ircul.user_nick(before, after)
		
		# If it was our primary nickname, try and regain it
		if after != conn.getnick() and before == wrap.nicks[0]:
			conn.nick(before)
	
	# -----------------------------------------------------------------------
	# Numeric 352 : WHO reply
	# -----------------------------------------------------------------------
	def _handle_whoreply(self, connid, conn, event):
		# chan ident host server nick ?modes? ?n realname?
		wrap = self.Conns[connid]
		chan = event.arguments[0].lower()
		ident, host = event.arguments[1:3]
		nick = event.arguments[4]
		modes = event.arguments[5]
		
		# Add this user to the userlist
		hostmask = '%s!%s@%s' % (nick, ident, host)
		wrap.ircul.user_joined(chan, hostmask)
		
		# Add any modes this user seems to have
		for sign in modes:
			mode = wrap.conn.features['user_modes_r'].get(sign, None)
			if mode is not None:
				wrap.ircul.user_add_mode(chan, nick, mode)
	
	# -----------------------------------------------------------------------
	# Numeric 315 : WHO reply
	# -----------------------------------------------------------------------
	def _handle_endofwho(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.arguments[0].lower()
		
		wrap.ircul._c[chan].synched = True
		
		tolog = 'Userlist synched for %s' % (event.arguments[0])
		self.connlog(connid, LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Numeric 353 : list of names in channel
	# -----------------------------------------------------------------------
	def _dont_handle_namreply(self, connid, conn, event):
		wrap = self.Conns[connid]
		chan = event.arguments[1].lower()
		
		# We need this the other way around
		sign_to_char = dict([(v, k) for k, v in wrap.conn.features['user_modes'].items()])
		
		# Add each nick to the channel user list
		for nick in event.arguments[2].split():
			if nick[0] in sign_to_char:
				wrap.ircul.user_joined(chan, nick[1:])
				wrap.ircul.user_add_mode(chan, nick[1:], sign_to_char[nick[0]])
			else:
				wrap.ircul.user_joined(chan, nick)
	
	# -----------------------------------------------------------------------
	# Our nickname is in use!
	# -----------------------------------------------------------------------
	def _handle_nicknameinuse(self, connid, conn, event):
		nick = event.arguments[0]
		
		self.Conns[connid].nicknameinuse(nick)
	
	# -----------------------------------------------------------------------
	# Various errors, all of which are saying that we can't join a channel.
	# -----------------------------------------------------------------------
	def _joinerror(self, connid, conn, event):
		chan = event.arguments[0].lower()
		
		# Try to join again soon
		data = [time.time(), connid, self.Conns[connid].connect_id, chan]
		self.__Rejoins.append(data)
	
	_handle_unavailresource = _joinerror
	_handle_channelisfull = _joinerror
	_handle_inviteonlychan = _joinerror
	_handle_bannedfromchan = _joinerror
	
	# -----------------------------------------------------------------------
	# Someone just said something in a channel we're in
	# -----------------------------------------------------------------------
	def _handle_pubmsg(self, connid, conn, event):
		chan = event.target.lower()
		wrap = self.Conns[connid]
		
		# Skip ignored people
		if self.Userlist.Has_Flag(event.userinfo, 'Global', 'ignore'):
			return
		
		# Strip any codes from the text
		text = RE_STRIP_CODES.sub('', event.arguments[0])
		
		# Strip leading and trailing spaces
		text = text.strip()
		
		# No text? Booo.
		if text == '':
			return
		
		# See if it's addressed to anyone
		m = RE_ADDRESSED.match(text)
		if m:
			to = m.group('nick')
			if to.lower() != conn.getnick().lower():
				return
			
			data = [wrap, IRCT_PUBLIC_D, event.userinfo, chan, m.group('text')]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
		
		# It's not addressed to anyone, so do whatever we do here
		else:
			# Maybe rewrite the text to look like a different command
			parts = text.lower().split(None, 1)
			
			# Look for exact commands
			if len(parts) == 1 and parts[0] in self.__Public_Exact:
				newtext = self.__Public_Exact[parts[0]]
				data = [wrap, IRCT_PUBLIC_D, event.userinfo, chan, newtext]
				
				tolog = "Rewrote public command '%s' to '%s'" % (text, newtext)
				self.putlog(LOG_DEBUG, tolog)
			
			# Look for param commands
			elif len(parts) == 2 and parts[0] in self.__Public_Param:
				newtext = '%s %s' % (self.__Public_Param[parts[0]], parts[1])
				data = [wrap, IRCT_PUBLIC_D, event.userinfo, chan, newtext]
				
				tolog = "Rewrote public command '%s' to '%s'" % (text, newtext)
				self.putlog(LOG_DEBUG, tolog)
			
			# Oh well, guess it's just public text
			else:
				data = [wrap, IRCT_PUBLIC, event.userinfo, chan, text]
			
			# Send the event
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone just said something to us in private!
	# -----------------------------------------------------------------------
	def _handle_privmsg(self, connid, conn, event):
		wrap = self.Conns[connid]
		
		# Stoned check
		if event.userinfo.nick == conn.getnick():
			wrap.stoned -= 1
		
		else:
			# Skip ignored people
			if self.Userlist.Has_Flag(event.userinfo, 'Global', 'ignore'):
				return
			
			# If we're ignoring strangers, skip them
			#if wrap.ignore_strangers == 1 and not wrap.ircul.user_in_any_chan(event.userinfo.nick):
			#	return
			
			# Strip any codes from the text
			text = RE_STRIP_CODES.sub('', event.arguments[0])
			# Strip leading and trailing spaces
			text = text.strip()
			# If we still have text, trigger the event
			if text != '':
				data = [wrap, IRCT_MSG, event.userinfo, None, text]
				self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone is sending us a CTCP
	# -----------------------------------------------------------------------
	def _handle_ctcp(self, connid, conn, event):
		# Ignore channel CTCPs
		if event.target != conn.getnick():
			return
		
		# Skip ignored people
		if self.Userlist.Has_Flag(event.userinfo, 'Global', 'ignore'):
			return
		
		
		first = event.arguments[0].upper()
		
		# Capitalise the arguments if there are any
		if len(event.arguments) == 2:
			rest = event.arguments[1].upper()
		else:
			rest = ''
		
		
		tolog = None
		
		# Someone wants to see what sort of CTCP stuff we can handle
		if first == 'CLIENTINFO':
			tolog = 'CTCP CLIENTINFO from %s' % (event.userinfo)
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			self.Conns[connid].ctcp_reply(event.userinfo.nick, 'CLIENTINFO PING VERSION')
		
		# Someone wants to see if we're lagged
		elif first == 'PING':
			tolog = 'CTCP PING from %s' % (event.userinfo)
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			# We only actually reply if they gave us some data
			if len(rest) > 0:
				reply = 'PING %s' % rest[:50]
				self.Conns[connid].ctcp_reply(event.userinfo.nick, reply)
		
		# Someone wants to know what we're running
		elif first == 'VERSION':
			tolog = 'CTCP VERSION from %s' % (event.userinfo)
			self.connlog(connid, LOG_ALWAYS, tolog)
			
			reply = 'VERSION blamehangle v%s - no space aliens were harmed in the making of this hangle.' % BH_VERSION
			self.Conns[connid].ctcp_reply(event.userinfo.nick, reply)
		
		# Someone wants us to rehash... better make sure they're not evil
		elif first == 'REHASH':
			# If they have access, rehash
			if self.Userlist.Has_Flag(event.userinfo, 'Global', 'admin'):
				tolog = "Admin %s requested a rehash." % (event.userinfo)
				self.connlog(connid, LOG_WARNING, tolog)
				
				self.Conns[connid].notice(event.userinfo.nick, 'Rehashing...')
				
				self.sendMessage('Postman', REQ_REHASH, [])
			
			# If not, cry
			else:
				tolog = "Unknown lamer %s requested rehash!" % (event.userinfo)
				self.connlog(connid, LOG_WARNING, tolog)
		
		# No idea, see if a plugin cares
		else:
			wrap = self.Conns[connid]
			data = [wrap, IRCT_CTCP, event.userinfo, None, first + rest]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Something wants to receive all IRC events, crazy
	def _message_REQ_IRC_EVENTS(self, message):
		self.__Handlers[message.source] = message.data
	
	# Something wants to send a privmsg
	def _message_REQ_PRIVMSG(self, message):
		conn, target, text = message.data
		
		if isinstance(conn, asyncIRC):
			self.privmsg(conn.connid, target, text)
		
		elif isinstance(conn, WrapConn):
			self.privmsg(conn.conn.connid, target, text)
		
		elif isinstance(conn, dict):
			for network, targets in conn.items():
				found = 0
				net = network.lower()
				for wrap in self.Conns.values():
					if wrap.name.lower() == net:
						# If we combine targets for this network, do that
						if wrap.combine_targets:
							max_targets = wrap.conn.features['max_targets']
							for i in range(0, len(targets), max_targets):
								target = ','.join(targets[i:i+max_targets])
								self.privmsg(wrap.conn.connid, target, text)
						# Oh well, do it the slow way
						else:
							for target in targets:
								self.privmsg(wrap.conn.connid, target, text)
						
						found = 1
						break
				
				if found == 0:
					tolog = "Invalid network in PRIVMSG from '%s': %s" % (message.source, net)
					self.putlog(LOG_WARNING, tolog)
		
		else:
			tolog = "Unknown REQ_PRIVMSG parameter type from %s: %s" % (message.source, type(conn))
			self.putlog(LOG_WARNING, tolog)
	
	# Someone wants some WrapConn objects
	def _message_REQ_WRAPS(self, message):
		wraps = {}
		
		for net in message.data:
			netl = net.lower()
			for wrap in self.Conns.values():
				if wrap.name.lower() == netl:
					wraps[net] = wrap
		
		self.sendMessage(message.source, REPLY_WRAPS, wraps)
	
	# Someone wants some stats
	def _message_GATHER_STATS(self, message):
		nets = 0
		chans = 0
		
		for wrap in self.Conns.values():
			nets += 1
			chans += len(wrap.ircul._c)
		
		message.data['irc_nets'] = nets
		message.data['irc_chans'] = chans
		
		self.sendMessage('DataMonkey', GATHER_STATS, message.data)

# ---------------------------------------------------------------------------
