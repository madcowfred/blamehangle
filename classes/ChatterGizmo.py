# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains ChatterGizmo, which does most of the grunt work for IRC
# connections.
# ---------------------------------------------------------------------------

import errno
import re
import select
import time
import types

from classes import irclib

from classes.Children import Child
from classes.Common import *
from classes.Constants import *
from classes.Userlist import Userlist
from classes.WrapConn import *

# ---------------------------------------------------------------------------

# bold | codes off | reverse | underline | 3 forms of colours
RE_STRIP_CODES = re.compile(r'(\x02|\x0F|\x16|\x1F|\x03\d{1,2},\d{1,2}|\x03\d{1,2}|\x03)')

# regexp to see if people are addressing someone
RE_ADDRESSED = re.compile(r'^(?P<nick>\S+)\s*[:;,>]\s*(?P<text>.+)$')

# ---------------------------------------------------------------------------
# Shiny way to look at a user.
# ---------------------------------------------------------------------------
class UserInfo:
	def __init__(self, hostmask):
		self.hostmask = hostmask
		
		self.nick, rest = hostmask.split('!')
		self.ident, self.host = rest.split('@')

# ---------------------------------------------------------------------------

class ChatterGizmo(Child):
	"""
	The IRC class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def setup(self):
		self.__ircobj = irclib.IRC()
		# Add handlers for any event we're supposed to handle
		for thing in dir(self):
			if not thing.startswith('_handle_'):
				continue
			event = thing[8:]
			self.__ircobj.add_global_handler(event, getattr(self, thing), -10)
		
		self.Conns = {}
		self.stopping = 0
		
		self.__Rejoins = []
		
		# Set up our public commands, if there are any
		self.__Setup_Public()
	
	# The bot has been rehashed.. re-load the global users info, and check if
	# there are any changes to the servers/channels we have been requested to
	# sit in
	def rehash(self):
		# Set up our public commands, if there are any
		self.__Setup_Public()
		
		# Get a list of our old networks
		old_nets = []
		for conn in self.Conns.keys():
			data = (conn, self.Conns[conn].network)
			old_nets.append(data)
		
		# Get a list of our new networks
		new_nets = [s for s in self.Config.sections() if s.startswith('network.')]
		
		# Work out which networks are new and which are old (heh)
		for conn, network in old_nets:
			if [section for section in new_nets if section == network]:
				# we are meant to stay on this network, check if we need to
				# join or part any channels
				old_chans = self.Conns[conn].users.channels()
				new_chans = self.Config.get(network, 'channels').split()
				
				# Leave any channels that are no longer in our config
				for chan in [chan for chan in old_chans if chan not in new_chans]:
					conn.part(chan)
				
				# And join any new ones
				self.Conns[conn].channels = new_chans
				self.Conns[conn].join_channels()
			
			# Quit and remove any gone networks
			else:
				self.Conns[conn].requested_quit = 1
				
				if self.Conns[conn].conn.status != STATUS_DISCONNECTED:
					self.Conns[conn].conn.quit('So long, and thanks for all the fish.')
				
				else:
					self._handle_disconnect(conn, None)
		
		# Connect to any newly added networks
		for section in new_nets:
			if not [network for conn, network in old_nets if network == section]:
				self.connect(section=section)
	
	def shutdown(self, message):
		quitmsg = 'Shutting down: %s' % message.data
		for wrap in self.Conns.values():
			if wrap.conn.status == STATUS_CONNECTED:
				wrap.conn.quit(quitmsg)
		
		self.stopping = 1
	
	# -----------------------------------------------------------------------
	# Set up any public triggers we might have
	def __Setup_Public(self):
		self.__Public_Exact = {}
		self.__Public_Param = {}
		
		for option in self.Config.options('public'):
			command, rewrite = self.Config.get('public', option).split(None, 1)
			
			# An 'exact' command
			if option.startswith('exact'):
				self.__Public_Exact[command] = rewrite
				tolog = "Added exact rewrite '%s' --> '%s'" % (command, rewrite)
			
			# A 'param' command
			elif option.startswith('param'):
				self.__Public_Param[command] = rewrite
				tolog = "Added param rewrite '%s' --> '%s'" % (command, rewrite)
			
			self.putlog(LOG_DEBUG, tolog)
	
	# -----------------------------------------------------------------------
	
	def run_once(self):
		self.connect()
	
	def run_sometimes(self, currtime):
		# Process any data from IRC
		try:
			self.__ircobj.process_once()
		
		except select.error, msg:
			if msg[0] == errno.EINTR:
				pass
		
		# Stop if we're all done
		if self.stopping:
			for wrap in self.Conns.values():
				if wrap.conn.status == STATUS_CONNECTED:
					return
			
			self.stopnow = 1
			return
		
		# See if we have to try rejoining any channels
		for rejoin in self.__Rejoins:
			last, conn, connect_id, chan = rejoin
			wrap = self.Conns[conn]
			
			if wrap.conn.status != STATUS_CONNECTED or wrap.connect_id != connect_id:
				self.__Rejoins.remove(rejoin)
				continue
			
			elif (currtime - last) >= 20:
				self.__Rejoins.remove(rejoin)
				conn.join(chan)
		
		# Do other stuff here
		for conn, wrap in self.Conns.items():
			wrap.run_sometimes(currtime)
	
	# -----------------------------------------------------------------------
	
	def connect(self, section=None):
		if section:
			options = {}
			for option in self.Config.options(section):
				options[option] = self.Config.get(section, option)
			
			conn = self.__ircobj.server()
			self.Conns[conn] = WrapConn(self, section, conn, options)
			self.Conns[conn].connect()
		
		else:
			networks = []
			for section in self.Config.sections():
				if section.startswith('network.'):
					networks.append(section)
			
			if not networks:
				raise Exception, 'No networks defined in config file'
			
			for network in networks:
				options = {}
				for option in self.Config.options(network):
					options[option] = self.Config.get(network, option)
				
				
				conn = self.__ircobj.server()
				self.Conns[conn] = WrapConn(self, network, conn, options)
			
				self.Conns[conn].connect()
	
	# -----------------------------------------------------------------------
	
	def privmsg(self, conn, nick, text):
		self.Conns[conn].privmsg(nick, text)
	
	def notice(self, conn, nick, text):
		self.Conns[conn].notice(nick, text)
	
	def connlog(self, conn, level, text):
		newtext = '(%s) %s' % (self.Conns[conn].options['name'], text)
		self.putlog(level, newtext)
	
	# -----------------------------------------------------------------------
	# Raw 001 - Welcome to the server, foo
	# -----------------------------------------------------------------------
	def _handle_welcome(self, conn, event):
		wrap = self.Conns[conn]
		
		wrap.connect_id += 1
		wrap.conn.status = STATUS_CONNECTED
		
		tolog = 'Connected to %s:%d' % wrap.server
		self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		# If we're supposed to use NickServ, do so
		_nick = wrap.options.get('nickserv_nick', None)
		_pass = wrap.options.get('nickserv_pass', None)
		
		if _nick and _pass:
			tolog = 'Identifying with %s' % (_nick)
			self.connlog(conn, LOG_ALWAYS, tolog)
			
			text = 'IDENTIFY %s' % (_pass)
			self.privmsg(conn, _nick, text)
		
		wrap.join_channels()
	
	# -----------------------------------------------------------------------
	# We just got disconnected from the server
	# -----------------------------------------------------------------------
	def _handle_disconnect(self, conn, event):
		self.Conns[conn].disconnected()
		self.Conns[conn].last_connect = time.time()
		
		self.connlog(conn, LOG_ALWAYS, 'Disconnected from server')
		
		if not self.stopping:
			if self.Conns[conn].requested_quit:
				tolog = 'Removing network!'
				self.connlog(conn, LOG_ALWAYS, tolog)
				
				del self.Conns[conn]
				del conn
	
	# It was bad.
	def _handle_error(self, conn, event):
		errormsg = event.target()
		
		m = re.match(r".* \((?P<error>.*?)\)$", errormsg)
		if m:
			errormsg = m.group('error')
		
		tolog = 'ERROR: %s' % (errormsg)
		self.connlog(conn, LOG_ALWAYS, tolog)
	
	# -----------------------------------------------------------------------
	# Someone just joined a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_join(self, conn, event):
		chan = event.target().lower()
		nick = irclib.nm_to_n(event.source())
		
		# Us
		if nick == conn.real_nickname:
			self.Conns[conn].users.joined(chan)
			
			tolog = "Joined %s" % chan
			self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Not us
		else:
			self.Conns[conn].users.joined(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just parted a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_part(self, conn, event):
		chan = event.target().lower()
		nick = irclib.nm_to_n(event.source())
		
		# Us
		if nick == conn.real_nickname:
			self.Conns[conn].users.parted(chan)
			
			tolog = 'Left %s' % chan
			self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Not us
		else:
			self.Conns[conn].users.parted(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just quit (including ourselves? not sure)
	# -----------------------------------------------------------------------
	def _handle_quit(self, conn, event):
		nick = irclib.nm_to_n(event.source())
		
		if nick != conn.real_nickname:
			self.Conns[conn].users.quit(nick)
			
			# If it was our primary nickname, try and regain it
			if nick == self.Conns[conn].nicks[0]:
				conn.nick(nick)
	
	# -----------------------------------------------------------------------
	# Someone just changed the mode on a channel we're in
	# -----------------------------------------------------------------------
	def _handle_mode(self, conn, event):
		chan = event.target().lower()
		
		modestring = ' '.join(event.arguments())
		modes = irclib.parse_channel_modes(modestring)
		
		for sign, mode, arg in modes:
			# We don't care about non-user modes
			if arg is None or mode not in 'ovh':
				continue
			
			if sign == '+':
				self.Conns[conn].users.add_mode(chan, arg, mode)
			elif sign == '-':
				self.Conns[conn].users.del_mode(chan, arg, mode)
	
	# -----------------------------------------------------------------------
	# Someone just invited us to a channel
	# -----------------------------------------------------------------------
	def _handle_invite(self, conn, event):
		chan = event.arguments()[0].lower()
		userinfo = UserInfo(event.source())
		
		if chan in self.Conns[conn].channels:
			tolog = '%s invited me to %s, joining...' % (userinfo.nick, chan)
			self.putlog(LOG_ALWAYS, tolog)
			conn.join(chan)
		else:
			tolog = '%s invited me to %s, which is NOT in my channel list!' % (userinfo.nick, chan)
			self.putlog(LOG_WARNING, tolog)
	
	# -----------------------------------------------------------------------
	# Someone was just kicked from a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_kick(self, conn, event):
		chan = event.target().lower()
		kicker = irclib.nm_to_n(event.source())
		kicked = event.arguments()[0]
		
		if kicked == conn.real_nickname:
			tolog = 'I just got kicked from %s by %s, rejoining...' % (chan, kicker)
			self.connlog(conn, LOG_ALWAYS, tolog)
			
			self.Conns[conn].users.parted(chan)
			conn.join(chan)
		
		else:
			self.Conns[conn].users.parted(chan, kicked)
	
	# -----------------------------------------------------------------------
	# Someone just changed their name (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_nick(self, conn, event):
		before = irclib.nm_to_n(event.source())
		after = event.target()
		
		# If it wasn't us
		if after != conn.real_nickname:
			self.Conns[conn].users.nick(before, after)
			
			# If it was our primary nickname, try and regain it
			if before == self.Conns[conn].nicks[0]:
				conn.nick(before)
	
	# -----------------------------------------------------------------------
	# Numeric 353 : list of names in channel
	# -----------------------------------------------------------------------
	def _handle_namreply(self, conn, event):
		chan = event.arguments()[1].lower()
		
		# Add each nick to the channel user list
		for nick in event.arguments()[2].split():
			if nick[0] in ('@', '+'):
				nick = nick[1:]
			
			self.Conns[conn].users.joined(chan, nick)
	
	# -----------------------------------------------------------------------
	# Our nickname is in use!
	# -----------------------------------------------------------------------
	def _handle_nicknameinuse(self, conn, event):
		nick = event.arguments()[0]
		
		self.Conns[conn].nicknameinuse(nick)
	
	# -----------------------------------------------------------------------
	# Various errors, all of which are saying that we can't join a channel.
	# -----------------------------------------------------------------------
	#for event in [	"unavailresource", "channelisfull", "inviteonlychan",
	#	"bannedfromchan", "badchannelkey" ]:
	def _joinerror(self, conn, event):
		chan = event.arguments()[0].lower()
		
		# Try to join again soon
		data = [time.time(), conn, self.Conns[conn].connect_id, chan]
		self.__Rejoins.append(data)
	
	_handle_unavailresource = _joinerror
	_handle_channelisfull = _joinerror
	_handle_inviteonlychan = _joinerror
	_handle_bannedfromchan = _joinerror
	
	# -----------------------------------------------------------------------
	# Someone just said something in a channel we're in
	# -----------------------------------------------------------------------
	def _handle_pubmsg(self, conn, event):
		chan = event.target().lower()
		userinfo = UserInfo(event.source())
		wrap = self.Conns[conn]
		
		# Don't do anything for ignored lamers
		#if self.__users.check_user_flags(userinfo, 'ignore'):
		if self.Userlist.Has_Flag(userinfo, 'Global', 'ignore'):
			return
		
		# Strip any codes from the text
		text = RE_STRIP_CODES.sub('', event.arguments()[0])
		
		# Strip leading and trailing spaces
		text = text.strip()
		
		# No text? Booo.
		if text == '':
			return
		
		# See if it's addressed to anyone
		m = RE_ADDRESSED.match(text)
		if m:
			to = m.group('nick')
			if to.lower() != conn.real_nickname.lower():
				return
			
			data = [wrap, IRCT_PUBLIC_D, userinfo, chan, m.group('text')]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
		
		# It's not addressed to anyone, so do whatever we do here
		else:
			# Maybe rewrite the text to look like a different command
			parts = text.lower().split(None, 1)
			
			# Look for exact commands
			if len(parts) == 1 and parts[0] in self.__Public_Exact:
				newtext = self.__Public_Exact[parts[0]]
				data = [wrap, IRCT_PUBLIC_D, userinfo, chan, newtext]
				
				tolog = "Rewrote public command '%s' to '%s'" % (text, newtext)
				self.putlog(LOG_DEBUG, tolog)
			
			# Look for param commands
			elif len(parts) == 2 and parts[0] in self.__Public_Param:
				newtext = '%s %s' % (self.__Public_Param[parts[0]], parts[1])
				data = [wrap, IRCT_PUBLIC_D, userinfo, chan, newtext]
				
				tolog = "Rewrote public command '%s' to '%s'" % (text, newtext)
				self.putlog(LOG_DEBUG, tolog)
			
			# Oh well, guess it's just public text
			else:
				data = [wrap, IRCT_PUBLIC, userinfo, chan, text]
			
			# Send the event
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone just said something to us in private!
	# -----------------------------------------------------------------------
	def _handle_privmsg(self, conn, event):
		userinfo = UserInfo(event.source())
		wrap = self.Conns[conn]
		
		# Stoned check
		if userinfo.nick == conn.real_nickname:
			wrap.stoned -= 1
		
		else:
			# Skip ignored people
			if self.Userlist.Has_Flag(userinfo, 'Global', 'ignore'):
				return
			
			# If we're ignoring strangers, skip them
			if wrap.ignore_strangers == 1 and not wrap.users.in_any_chan(userinfo.nick):
				return
			
			# Strip any codes from the text
			text = RE_STRIP_CODES.sub('', event.arguments()[0])
			# Strip leading and trailing spaces
			text = text.strip()
			
			if text != '':
				data = [wrap, IRCT_MSG, userinfo, None, text]
				self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone is sending us a CTCP
	# -----------------------------------------------------------------------
	def _handle_ctcp(self, conn, event):
		# Ignore channel CTCPs
		if event.target() != conn.real_nickname:
			return
		
		
		userinfo = UserInfo(event.source())
		
		if self.Userlist.Has_Flag(userinfo, 'Global', 'ignore'):
			return
		
		# Ignore them if they're not on any of our channels
		#if self.__Nice_Person_Check(userinfo):
		#	return
		
		
		first = event.arguments()[0].upper()
		
		# Capitalise the arguments if there are any
		if len(event.arguments()) == 2:
			rest = event.arguments()[1].upper()
		else:
			rest = ''
		
		
		if first == 'VERSION':
			self.Conns[conn].ctcp_reply(userinfo.nick, "VERSION blamehangle v" + BH_VERSION)
		
		elif first == 'PING':
			if len(rest) > 0:
				reply = 'PING %s' % rest
				self.Conns[conn].ctcp_reply(userinfo.nick, reply)
		
		elif first == 'CLIENTINFO':
			self.Conns[conn].ctcp_reply(userinfo.nick, 'CLIENTINFO PING VERSION')
		
		elif first == 'REHASH':
			# If they have access, rehash
			if self.Userlist.Has_Flag(userinfo, 'Global', 'admin'):
				tolog = "Admin '%s' (%s@%s) requested a rehash." % (userinfo.nick, userinfo.ident, userinfo.host)
				self.sendMessage('Postman', REQ_LOAD_CONFIG, [])
			# If not, cry
			else:
				tolog = "Unknown lamer '%s' (%s@%s) requested rehash!" % (userinfo.nick, userinfo.ident, userinfo.host)
			
			# Log it
			self.connlog(conn, LOG_WARNING, tolog)
		
		else:
			wrap = self.Conns[conn]
			data = [wrap, IRCT_CTCP, userinfo, None, first + rest]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	
	def _message_REQ_PRIVMSG(self, message):
		conn, target, text = message.data
		
		if isinstance(conn, irclib.ServerConnection):
			self.privmsg(conn, target, text)

		elif isinstance(conn, WrapConn):
			for server_conn in self.Conns:
				if self.Conns[server_conn] == conn:
					self.privmsg(server_conn, target, text)
		
		elif type(conn) == types.DictType:
			for network, targets in conn.items():
				net = network.lower()
				for wrap in self.Conns.values():
					if wrap.options['name'].lower() == net:
						for target in targets:
							self.privmsg(wrap.conn, target, text)
						break
		
		else:
			raise TypeError, 'unknown parameter type'
