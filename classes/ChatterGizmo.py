
__version__ = '$Id$'

# ---------------------------------------------------------------------------

import errno
import re
import select

from classes.Common import *
from classes.Constants import *

from classes import irclib

from classes.Children import Child
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
	
	Conns = {}
	
	def setup(self):
		print 'setup'

		self.__ircobj = irclib.IRC()
		# Add handlers for each event in this array to call handle_event
		#for event in [	"disconnect", "welcome", "namreply", "nicknameinuse", "join",
		#				"part", "kick", "quit", "nick", "ctcp", "privmsg", "privnotice" ]:
		for event in [ 'welcome', 'namreply', 'join', 'part', 'kick', 'quit',
			'pubmsg', 'privmsg' ]:
			self.__ircobj.add_global_handler(event, getattr(self, "_handle_" + event), -10)
		
		self.connect()
	
	def run_always(self):
		try:
			self.__ircobj.process_once()
		
		except select.error, msg:
			if msg[0] == errno.EINTR:
				pass
	
	def run_sometimes(self, currtime):
		pass
	
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
			self.Conns[conn] = WrapConn(conn, options)
			
			self.Conns[conn].connect()
	
	# -----------------------------------------------------------------------
	
	def privmsg(self, conn, nick, text):
		if self.Conns[conn].status == STATUS_CONNECTED:
			conn.privmsg(nick, text)
	
	def notice(self, conn, nick, text):
		if self.Conns[conn].status == STATUS_CONNECTED:
			conn.notice(nick, text)
	
	def connlog(self, conn, level, text):
		newtext = '(%s) %s' % (self.Conns[conn].options['name'], text)
		self.putlog(level, newtext)
	
	# -----------------------------------------------------------------------
	
	def _handle_welcome(self, conn, event):
		tolog = 'Connected to %s:%d' % self.Conns[conn].server
		self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Start the stoned timer thing
		#self.__Stoned_Check()
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		self.Conns[conn].join_channels()
	
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
			self.Conns[conn].parted(chan)
			
			tolog = 'Left %s' % chan
			self.connlog(conn, LOG_ALWAYS, tolog)
		
		# Not us
		else:
			self.Conns[conn].parted(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just quit (including ourselves? not sure)
	# -----------------------------------------------------------------------
	def _handle_quit(self, conn, event):
		nick = irclib.nm_to_n(event.source())
		
		if nick != conn.real_nickname:
			self.Conns[conn].users.quit(nick)
			
			# If it was our primary nickname, try and regain it
			#if nick == self.nicknames[0]:
			#	self.connection.nick(nick)
	
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
	# Someone just said something in a channel we're in
	# -----------------------------------------------------------------------
	def _handle_pubmsg(self, conn, event):
		chan = event.target().lower()
		userinfo = UserInfo(event.source())
		
		# Strip any codes from the text
		text = STRIP_CODES.sub('', event.arguments()[0])
		
		if text == '':
			return
		
		# See if it's addressed to anyone
		addr = 0
		for i in range(1, min(10, len(text))):
			if text[i] in (':;,-'):
				if text[i+1] == ' ':
					addr = i+2
				else:
					addr = i+1
		
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
		#chan = event.target().lower()
		userinfo = UserInfo(event.source())
		
		# Strip any codes from the text
		text = STRIP_CODES.sub('', event.arguments()[0])
		
		if text == '':
			return
		
		data = [conn, IRCT_MSG, userinfo, None, text]
		self.sendMessage('PluginHandler', IRC_EVENT, data)
