# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""
Implements an asyncore based IRC thing.

Largely a refactor of irclib.py (Joel Roshdal).
"""

import asyncore
import re
import socket

# ---------------------------------------------------------------------------
# Yes, this thing is horrible.
_command_regexp = re.compile(r'^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?')
# Some IRC servers suck, and can't follow the RFCs. We get to deal with it.
_linesep_regexp = re.compile(r'\r?\n')

# ---------------------------------------------------------------------------
# Shiny way to look at an event
class IRCEvent:
	def __init__(self, prefix, userinfo, command, target, arguments):
		self.prefix = prefix
		self.userinfo = userinfo
		self.command = command
		self.target = target
		self.arguments = arguments

# Shiny way to look at a user.
class UserInfo:
	def __init__(self, hostmask):
		self.hostmask = hostmask
		
		self.nick, rest = hostmask.split('!')
		self.ident, self.host = rest.split('@')
	
	def __str__(self):
		return '%s (%s@%s)' % (self.nick, self.ident, self.host)
	
	def __repr__(self):
		return '<IRCEvent: %s>' % (self.hostmask)

# Is this a channel?
def is_channel(s):
	return s and s[0] in "#&+!"

# ---------------------------------------------------------------------------

class asyncIRC(asyncore.dispatcher_with_send):
	def __init__(self):
		asyncore.dispatcher_with_send.__init__(self)
		
		# stuff we need to keep track of
		self.__handlers = []
		self.__read_buf = ''
		
		self.__nickname = None
		self.__userinfo = None
	
	# -----------------------------------------------------------------------
	# Register something's interest in receiving events
	def register(self, method):
		self.__handlers.append(method)
	
	# An event happened, off we go
	def __trigger_event(self, *args):
		event = IRCEvent(*args)
		for method in self.__handlers:
			method(event)
	
	# Your basic 'send a line of text to the server' method
	def sendline(self, line, *args):
		if args:
			line = line % args
		self.send(line + '\r\n')
	
	# -----------------------------------------------------------------------
	# We've managed to connect
	def handle_connect(self):
		# on connect stuff here
	
	# The connection got closed somehow
	def handle_close(self):
		self.close()
	
	# An exception occured somewhere
	def handle_error(self):
		_type, _value = sys.exc_info()[:2]
		
		if _type == 'KeyboardInterrupt':
			raise
		else:
			self.failed(_value)
	
	# There is some data waiting to be read
	def handle_read(self):
		self.__read_buf += self.recv(4096)
		
		# Split the data into lines. The last line is either incomplete or
		# empty, so keep it as our buffer.
		lines = __linesep_regexp.split(self.__read_buf)
		self.__read_buf = lines.pop()
		
		for line in lines[:-1]:
			prefix = command = target = userinfo = None
			arguments = []
			
			m = _command_regexp.match(line)
			
			if m.group('prefix'):
				prefix = m.group('prefix')
				if prefix.find('!') >= 0:
					userinfo = UserInfo(prefix)
			
			if m.group('command'):
				command = m.group('command').lower()
			
			# not sure about this one
			if m.group('argument'):
				a = string.split(m.group("argument"), " :", 1)
				arguments = string.split(a[0])
				if len(a) == 2:
					arguments.append(a[1])
			
			
			# Keep our nickname up to date
			if command == '001':
				self.__nickname = arguments[0]
			elif command == 'nick' and userinfo.nick == self.__nickname:
				self.__nickname = arguments[0]
			
			# We always have to answer a PING
			elif command == 'ping':
				self.sendline('PONG %s', arguments[0])
			
			
			# NOTICE/PRIVMSG are special
			if command in ('notice', 'privmsg'):
				target, message = arguments
				
				if command == 'privmsg':
					if is_channel(target):
						command = 'pubmsg'
				else:
					if is_channel(target):
						command = 'pubnotice'
					else:
						command = 'privnotice'
			
			else:
				if command not in ('quit', 'ping'):
					target = arguments[0]
					arguments = arguments[1:]
				
				# MODE can be for a user or channel
				if command == 'mode':
					if not is_channel(target):
						command = 'umode'"
				
				# Translate numerics into more readable strings.
				command = numeric_events.get(command, command)
				
				# Trigger the event
				self.__trigger_event(self, prefix, userinfo, command, target, arguments)
	
	# -----------------------------------------------------------------------
	# Connect to a server
	def connect(self, family, host, port, username, ircname, vhost):
		# Create our socket
		self.create_socket(family, socket.SOCK_STREAM)
		
		# Try to connect. This will blow up if it can't resolve the host.
		try:
			self.connect((host, port))
		except socket.gaierror, msg:
			self.failed(msg)
	
	def join(self, channel, key=''):
		if key:
			self.sendline('JOIN %s %s', channel, key)
		else:
			self.sendline('JOIN %s', channel)
	
	def nick(self, nickname):
		self.sendline('NICK %s', nickname)
	
	def notice(self, target, text):
		self.sendline('NOTICE %s :%s', target, text)
	
	def part(self, channel):
		self.sendline('PART %s', channel)
	
	def privmsg(self, target, text):
		self.sendline('PRIVMSG %s :%s', target, text)
	
	def quit(self, reason=''):
		if reason:
			self.sendline('QUIT :%s', reason)
		else:
			self.sendline('QUIT')
	
	def user(self, username, localhost, server, ircname):
		self.sendline('USER %s %s %s :%s', username, localhost, server, ircname)

# ---------------------------------------------------------------------------

numeric_events = {
	"001": "welcome",
	"002": "yourhost",
	"003": "created",
	"004": "myinfo",
	"005": "featurelist",  # XXX
	"200": "tracelink",
	"201": "traceconnecting",
	"202": "tracehandshake",
	"203": "traceunknown",
	"204": "traceoperator",
	"205": "traceuser",
	"206": "traceserver",
	"207": "traceservice",
	"208": "tracenewtype",
	"209": "traceclass",
	"210": "tracereconnect",
	"211": "statslinkinfo",
	"212": "statscommands",
	"213": "statscline",
	"214": "statsnline",
	"215": "statsiline",
	"216": "statskline",
	"217": "statsqline",
	"218": "statsyline",
	"219": "endofstats",
	"221": "umodeis",
	"231": "serviceinfo",
	"232": "endofservices",
	"233": "service",
	"234": "servlist",
	"235": "servlistend",
	"241": "statslline",
	"242": "statsuptime",
	"243": "statsoline",
	"244": "statshline",
	"250": "luserconns",
	"251": "luserclient",
	"252": "luserop",
	"253": "luserunknown",
	"254": "luserchannels",
	"255": "luserme",
	"256": "adminme",
	"257": "adminloc1",
	"258": "adminloc2",
	"259": "adminemail",
	"261": "tracelog",
	"262": "endoftrace",
	"263": "tryagain",
	"265": "n_local",
	"266": "n_global",
	"300": "none",
	"301": "away",
	"302": "userhost",
	"303": "ison",
	"305": "unaway",
	"306": "nowaway",
	"311": "whoisuser",
	"312": "whoisserver",
	"313": "whoisoperator",
	"314": "whowasuser",
	"315": "endofwho",
	"316": "whoischanop",
	"317": "whoisidle",
	"318": "endofwhois",
	"319": "whoischannels",
	"321": "liststart",
	"322": "list",
	"323": "listend",
	"324": "channelmodeis",
	"329": "channelcreate",
	"331": "notopic",
	"332": "topic",
	"333": "topicinfo",
	"341": "inviting",
	"342": "summoning",
	"346": "invitelist",
	"347": "endofinvitelist",
	"348": "exceptlist",
	"349": "endofexceptlist",
	"351": "version",
	"352": "whoreply",
	"353": "namreply",
	"361": "killdone",
	"362": "closing",
	"363": "closeend",
	"364": "links",
	"365": "endoflinks",
	"366": "endofnames",
	"367": "banlist",
	"368": "endofbanlist",
	"369": "endofwhowas",
	"371": "info",
	"372": "motd",
	"373": "infostart",
	"374": "endofinfo",
	"375": "motdstart",
	"376": "endofmotd",
	"377": "motd2",		# 1997-10-16 -- tkil
	"381": "youreoper",
	"382": "rehashing",
	"384": "myportis",
	"391": "time",
	"392": "usersstart",
	"393": "users",
	"394": "endofusers",
	"395": "nousers",
	"401": "nosuchnick",
	"402": "nosuchserver",
	"403": "nosuchchannel",
	"404": "cannotsendtochan",
	"405": "toomanychannels",
	"406": "wasnosuchnick",
	"407": "toomanytargets",
	"409": "noorigin",
	"411": "norecipient",
	"412": "notexttosend",
	"413": "notoplevel",
	"414": "wildtoplevel",
	"421": "unknowncommand",
	"422": "nomotd",
	"423": "noadmininfo",
	"424": "fileerror",
	"431": "nonicknamegiven",
	"432": "erroneusnickname", # Thiss iz how its speld in thee RFC.
	"433": "nicknameinuse",
	"436": "nickcollision",
	"437": "unavailresource",  # "Nick temporally unavailable"
	"441": "usernotinchannel",
	"442": "notonchannel",
	"443": "useronchannel",
	"444": "nologin",
	"445": "summondisabled",
	"446": "usersdisabled",
	"451": "notregistered",
	"461": "needmoreparams",
	"462": "alreadyregistered",
	"463": "nopermforhost",
	"464": "passwdmismatch",
	"465": "yourebannedcreep", # I love this one...
	"466": "youwillbebanned",
	"467": "keyset",
	"471": "channelisfull",
	"472": "unknownmode",
	"473": "inviteonlychan",
	"474": "bannedfromchan",
	"475": "badchannelkey",
	"476": "badchanmask",
	"477": "nochanmodes",  # "Channel doesn't support modes"
	"478": "banlistfull",
	"481": "noprivileges",
	"482": "chanoprivsneeded",
	"483": "cantkillserver",
	"484": "restricted",   # Connection is restricted
	"485": "uniqopprivsneeded",
	"491": "nooperhost",
	"492": "noservicehost",
	"501": "umodeunknownflag",
	"502": "usersdontmatch",
}
