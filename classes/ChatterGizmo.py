import errno
import select

from classes import irclib

from classes.Userlist import Userlist
from classes.WrapConn import *

# ---------------------------------------------------------------------------

class ChatterGizmo:
	"""
	The IRC class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def __init__(self, Config):
		self.Config = Config
		
		self.__ircobj = irclib.IRC()
		self.Conns = {}
	
	def main_loop(self):
		try:
			self.__ircobj.process_once()
		
		except select.error, msg:
			if msg[0] == errno.EINTR:
				pass
	
	# -----------------------------------------------------------------------
	
	def connect(self):
		networks = []
		for section in self.Config.sections():
			if section.startswith('network.'):
				networks.push(section)
		
		if not networks:
			#putlog(no networks? how can this be?!)
			print 'erk, no networks'
			return
		
		for network in networks:
			options = {}
			for option in self.Config.options(network):
				options[option] = self.Config.get(network, option)
			
			conn = self.__ircobj.server()
			self.Conns[conn] = WrapConn(conn, options)
			
			self.Conns[conn].do_connect()
	
	# -----------------------------------------------------------------------
	
	def privmsg(self, conn, nick, text):
		if self.Conns[conn].status == STATUS_CONNECTED:
			conn.privmsg(nick, text)
	
	def notice(self, conn, nick, text):
		if self.Conns[conn].status == STATUS_CONNECTED:
			conn.notice(nick, text)
	
	# -----------------------------------------------------------------------
	
	def _handle_welcome(self, conn, event):
		#tolog = 'Connected to %s' % self.server_list[0]
		#self.putlog(LOG_ALWAYS, tolog)
		
		# Start the stoned timer thing
		#self.__Stoned_Check()
		
		# Tell FileMonster what our local IP is
		#self.sendMessage('FileMonster', REPLY_LOCALADDR, self.connection.socket.getsockname())
		
		print 'Welcome to Floston Paradise!'
		
		for wrap in self.Conns.values():
			wrap.join_channels()
	
	# -----------------------------------------------------------------------
	# Someone just joined a channel (including ourselves)
	# -----------------------------------------------------------------------
	def _handle_join(self, conn, event):
		chan = event.target().lower()
		nick = irclib.nm_to_n(event.source())
		
		# Us
		if nick == conn.real_nickname:
			self.Conns[conn].users.joined(chan)
			
			#tolog = "Joined %s" % chan
			#self.putlog(LOG_ALWAYS, tolog)
		
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
			
			#tolog = 'Left %s' % chan
			#self.putlog(LOG_ALWAYS, tolog)
		
		# Not us
		else:
			self.Conns[conn].parted(chan, nick)
	
	# -----------------------------------------------------------------------
	# Someone just quit (including ourselves? not sure)
	# -----------------------------------------------------------------------
	def _handle_quit(self, conn, event):
		nick = irclib.nm_to_n(event.source())
		
		if nick != connection.real_nickname:
			self.Conns[conn].users.quit(nick)
			
			# If the user has left all our channels, tell FileMonster
			#if not self.__Users.in_any_chan(nick):
			#	self.sendMessage('FileMonster', USER_LEFT, nick)
			
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
		
		if kicked == connection.real_nickname:
			#tolog = 'I just got kicked from %s by %s, rejoining...' % (chan, kicker)
			#self.putlog(LOG_ALWAYS, tolog)
			
			self.Conns[conn].users.parted(chan)
			conn.join(chan)
		
		else:
			self.__Users.parted(chan, kicked)
			
			# If the user has left all our channels, tell FileMonster
			#if not self.__Users.in_any_chan(nick):
			#	self.sendMessage('FileMonster', USER_LEFT, nick)
	
	# -----------------------------------------------------------------------
	# Numeric 353 : list of names in channel
	# -----------------------------------------------------------------------
	def _handle_namreply(self, conn, event):
		chan = event.arguments()[1].lower()
		
		# Add each nick to the channel user list
		for nick in event.arguments()[2].split():
			if nick[0] in ('@', '+'):
				nick = nick[1:]
			
			self.Conns[conn].joined(chan, nick)
