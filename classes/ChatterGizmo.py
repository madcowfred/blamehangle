
__version__ = '$Id$'

# ---------------------------------------------------------------------------

import errno
import re
import select
import types

from classes import irclib

from classes.Children import Child
from classes.Common import *
from classes.Constants import *
from classes.Userlist import Userlist
from classes.WrapConn import *

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
	
	def shutdown(self, message):
		quitmsg = 'Shutting down: %s' % message.data
		for wrap in self.Conns.values():
			if wrap.status == STATUS_CONNECTED:
				wrap.conn.quit(quitmsg)
		
		self.stopping = 1
	
	# -----------------------------------------------------------------------
	
	def run_once(self):
		self.connect()
	
	def run_sometimes(self, currtime):
		for conn, wrap in self.Conns.items():
			if wrap.status == STATUS_DISCONNECTED and (currtime - wrap.last_connect) >= 5:
				wrap.jump_server()
			
			elif wrap.status == STATUS_CONNECTING and (currtime - wrap.last_connect) >= 30:
				self.connlog(conn, LOG_ALWAYS, 'Connection failed: connection timed out')
				wrap.jump_server()
			
			elif wrap.status == STATUS_CONNECTED:
				wrap.run_sometimes(currtime)
	
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
	
	def connect(self):
		networks = []
		for section in self.Config.sections():
			if section.startswith('network.'):
				networks.append(section)
		
		if not networks:
			self.putlog(LOG_ALWAYS, 'no networks? how can this be?!')
			return
		
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
		tolog = 'Connected to %s:%d' % self.Conns[conn].server
		self.Conns[conn].status = STATUS_CONNECTED
		self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Start the stoned timer thing
		#self.__Stoned_Check()
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		self.Conns[conn].join_channels()
	
	# -----------------------------------------------------------------------
	# We just got disconnected from the server
	# -----------------------------------------------------------------------
	def _handle_disconnect(self, conn, event):
		self.Conns[conn].disconnected()
		self.Conns[conn].last_connect = time.time()
		
		self.connlog(conn, LOG_ALWAYS, 'Disconnected from server')
	
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
	# Someone just said something in a channel we're in
	# -----------------------------------------------------------------------
	def _handle_pubmsg(self, conn, event):
		chan = event.target().lower()
		userinfo = UserInfo(event.source())
		
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
		
		# It's probably addressed to someone, see if it's us
		if addr:
			if not text.startswith(conn.real_nickname):
				return
			
			text = text[addr:]
			
			data = [conn, IRCT_PUBLIC_D, userinfo, chan, text]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
		
		# It's not addressed to anyone, so do whatever we do here
		else:
			data = [conn, IRCT_PUBLIC, userinfo, chan, text]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone just said something to us in private!
	# -----------------------------------------------------------------------
	def _handle_privmsg(self, conn, event):
		userinfo = UserInfo(event.source())
		
		# Strip any codes from the text
		text = STRIP_CODES.sub('', event.arguments()[0])
		
		if text == '':
			return
		
		data = [conn, IRCT_MSG, userinfo, None, text]
		self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	# Someone is sending us a CTCP
	# -----------------------------------------------------------------------
	def _handle_ctcp(self, conn, event):
		# Ignore channel CTCPs
		if event.target().startswith('#'):
			return
		
		
		userinfo = UserInfo(event.source())
		
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
		
		else:
			data = [conn, IRCT_CTCP, userinfo, None, first + rest]
			self.sendMessage('PluginHandler', IRC_EVENT, data)
	
	# -----------------------------------------------------------------------
	
	def _message_REQ_PRIVMSG(self, message):
		conn, target, text = message.data
		
		if isinstance(conn, irclib.ServerConnection):
			self.privmsg(conn, target, text)
		
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
