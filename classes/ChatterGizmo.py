
__version__ = '$Id$'

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
from classes.Users import *

# ---------------------------------------------------------------------------

TIMER_RECONNECT = 'TIMER_RECONNECT'
TIMER_TIMED_OUT = 'TIMER_TIMED_OUT'
TIMER_STONED_CHECK = 'TIMER_STONED_CHECK'

INTERVAL_STONED_CHECK = 30

# ---------------------------------------------------------------------------

# bold | codes off | reverse | underline | 3 forms of colours
STRIP_CODES = re.compile(r'(\x02|\x0F|\x16|\x1F|\x03\d{1,2},\d{1,2}|\x03\d{1,2}|\x03)')

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

		self.__users = HangleUserList(self, 'GlobalUsers')
	
	# The bot has been rehashed.. re-load the global users info, and check if
	# there are any changes to the servers/channels we have been requested to
	# sit in
	def rehash(self):
		self.__users = HangleUserList(self, 'GlobalUsers')

		old_nets = []
		nets = []
		for conn in self.Conns:
			old_nets.append((conn, self.Conns[conn].options['name']))
		
		for section in self.Config.sections():
			if section.startswith('network.'):
				nets.append((section, self.Config.get(section, 'name')))

		for conn, net in old_nets:
			if net not in [name for section, name in nets]:
				# this network has been removed from our config
				for wrap in self.Conns.values():
					if self.Conns[conn] == wrap and wrap.status == STATUS_CONNECTED:
						wrap.conn.quit('bye')
						wrap.requested_quit = 1
						
			else:
				# we are meant to stay on this network, check if we need to
				# join or part any channels
				old_chans = self.Conns[conn].users.channels()
				chans = self.Config.get(section, 'channels').split()

				for chan in old_chans:
					if chan not in chans:
						# we are no longer supposed to be in this channel
						conn.part(chan)
				
				self.Conns[conn].channels = chans
				self.Conns[conn].join_channels()

		for section, net in nets:
			if net not in [name for conn, name in old_nets]:
				# this is a new network that has been added to our config
				self.connect(section=section)
	
	# -----------------------------------------------------------------------
	
	def shutdown(self, message):
		quitmsg = 'Shutting down: %s' % message.data
		for wrap in self.Conns.values():
			if wrap.status == STATUS_CONNECTED:
				wrap.conn.quit(quitmsg)
		
		self.stopping = 1
	
	# -----------------------------------------------------------------------
	
	def run_once(self):
		#self.addTimer('moo', 5, 'cow')
		
		self.connect()
	
	def run_sometimes(self, currtime):
		# See if we have to try rejoining any channels
		for rejoin in self.__Rejoins:
			last, conn, connect_id, chan = rejoin
			wrap = self.Conns[conn]
			
			if wrap.status != STATUS_CONNECTED or wrap.connect_id != connect_id:
				self.__Rejoins.remove(rejoin)
				continue
			
			elif (currtime - last) >= 20:
				self.__Rejoins.remove(rejoin)
				conn.join(chan)
		
		# Do other stuff here
		for conn, wrap in self.Conns.items():
			if wrap.status == STATUS_CONNECTED:
				wrap.run_sometimes(currtime)
	
	# Process any data from IRC
	def run_always(self):
		try:
			self.__ircobj.process_once()
		
		except select.error, msg:
			if msg[0] == errno.EINTR:
				pass
		
		if self.stopping:
			for wrap in self.Conns.values():
				if wrap.status == STATUS_CONNECTED:
					return
			
			self.stopnow = 1
	
	# -----------------------------------------------------------------------
	
	def connect(self, section=None):
		if section:
			options = {}
			for option in self.Config.options(section):
				options[option] = self.Config.get(section, option)

			conn = self.__ircobj.server()
			self.Conns[conn] = WrapConn(self, conn, options)
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
				self.Conns[conn] = WrapConn(self, conn, options)
			
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
		wrap.status = STATUS_CONNECTED
		
		tolog = 'Connected to %s:%d' % wrap.server
		self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Start the stoned timer thing
		self.addTimer(TIMER_STONED_CHECK, INTERVAL_STONED_CHECK, conn, wrap.connect_id)
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
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
				del self.Conns[conn]
				del conn
			else:
				self.addTimer(TIMER_RECONNECT, 5, conn)
	
	# It was bad.
	def _handle_error(self, conn, event):
		errormsg = event.target()
		
		m = re.match(r".* \((?P<error>.*?)\)$", errormsg)
		if m:
			errormsg = m.group('error')
		
		tolog = 'ERROR: %s' % errormsg
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

		if self.__users.check_user_flags(userinfo, 'ignore'):
			return
		
		# Strip any codes from the text
		text = STRIP_CODES.sub('', event.arguments()[0])
		
		# Strip leading and trailing spaces
		text = text.strip()
		
		if text == '':
			return
		
		# See if it's addressed to anyone
		addr = 0
		end = min(10, len(text))
		for i in range(1, end):
			if text[i] in (':;,'):
				if (i + 1) < end and text[i+1] == ' ':
					addr = i+2
				else:
					addr = i+1
				break
		
		wrap = self.Conns[conn]
		
		# It's probably addressed to someone, see if it's us
		if addr:
			if not text[:addr-2].lower() == conn.real_nickname.lower():
				return
			
			text = text[addr:]
			
			data = [wrap, IRCT_PUBLIC_D, userinfo, chan, text]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
		
		# It's not addressed to anyone, so do whatever we do here
		else:
			data = [wrap, IRCT_PUBLIC, userinfo, chan, text]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone just said something to us in private!
	# -----------------------------------------------------------------------
	def _handle_privmsg(self, conn, event):
		userinfo = UserInfo(event.source())
		
		if self.__users.check_user_flags(userinfo, 'ignore'):
			return
		
		# Strip any codes from the text
		text = STRIP_CODES.sub('', event.arguments()[0])
		
		# Strip leading and trailing spaces
		text = text.strip()
		
		if text == '':
			return
		
		wrap = self.Conns[conn]
		
		# Stoned check
		if userinfo.nick == conn.real_nickname:
			wrap.stoned -= 1
		
		# Not a stoned check
		else:
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
		
		if self.__users.check_user_flags(userinfo, 'ignore'):
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
			if self.__users.check_user_flags(userinfo, 'admin'):
				self.sendMessage('Postman', REQ_LOAD_CONFIG, [])
		
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
	
	# A timer has triggered, yay
	def _message_REPLY_TIMER_TRIGGER(self, message):
		ident, data = message.data
		
		if ident == TIMER_RECONNECT:
			conn = data[0]
			self.Conns[conn].jump_server()
		
		elif ident == TIMER_STONED_CHECK:
			conn, connect_id = data
			wrap = self.Conns[conn]
			
			# Same connection, do the increment check
			if connect_id == wrap.connect_id:
				wrap.stoned += 1
				if wrap.stoned >= 4:
					conn.disconnect()
					return
			
			self.addTimer(TIMER_STONED_CHECK, INTERVAL_STONED_CHECK, conn, wrap.connect_id)
			self.privmsg(conn, conn.real_nickname, 'stoned check!')
		
		#elif ident == TIMER_TIMED_OUT:
		#	conn = data[0]
		#	self.connlog(conn, LOG_ALWAYS, 'Connection failed: connection timed out')
		#	
		#	self._handle_disconnect(self, conn, event):
		#	
		#	if conn.sock:
		#		conn.sock.close()
		#	
		#	self.Conns[conn].disconnected()
		#	conn.disconnect()
		#	
		#	elif wrap.status == STATUS_CONNECTING and (currtime - wrap.last_connect) >= 30:
		#		self.connlog(conn, LOG_ALWAYS, 'Connection failed: connection timed out')
		#		wrap.jump_server()
