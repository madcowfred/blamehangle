# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains classes and constants used in most (or all)
# of the other files.
# ---------------------------------------------------------------------------

import os, re, time, types

# ---------------------------------------------------------------------------
# Generic Message object that gets passed around the queues.
# ---------------------------------------------------------------------------
class Message:
	def __init__(self, source, targets, ident, data):
		self.source = source
		self.ident = ident
		self.data = data
		
		
		# Do some type checking, since people will feed us all sorts of types
		# of targets.
		t = type(targets)
		
		if t == types.NoneType:
			self.targets = []
			self.targetstring = 'ALL'
		
		elif t in (types.ListType, types.TupleType):
			self.targets = targets
			if targets:
				self.targetstring = ', '.join(targets)
			else:
				self.targetstring = 'ALL'
		
		elif t == types.StringType:
			self.targets = [targets]
			self.targetstring = targets
		
		else:
			print 'WTF? Invalid targets type: %s' % t
	
	# Return a printable string with info about ourself, including
	# how long it's been since we were sent.
	def __str__(self):
		return '%s --> %s: (%s) %s' % (self.source, self.targetstring, self.ident, self.data)


# ---------------------------------------------------------------------------
# Shiny way to look at a user.
# ---------------------------------------------------------------------------
class UserInfo:
	def __init__(self, hostmask):
		self.hostmask = hostmask
		
		self.nick, rest = hostmask.split('!')
		self.ident, self.host = rest.split('@')

# ---------------------------------------------------------------------------
# Returns a nicely formatted size for display.
# ---------------------------------------------------------------------------
def Nice_Size(bytes):
	bytes = float(bytes)
	
	if bytes < 1024:
		return '<1KB'
	elif bytes < (1024 * 1024):
		return '%dKB' % (bytes / 1024)
	else:
		return '%.1fMB' % (bytes / 1024.0 / 1024.0)

# ---------------------------------------------------------------------------
# Strip all non-numeric characters from a number
# ---------------------------------------------------------------------------
def Number(num):
	p = re.compile("\D")
	sanenum = p.sub('', str(num))
	
	if sanenum:
		return long(sanenum)
	else:
		return 0

# ---------------------------------------------------------------------------
# Make a "safe" filename that is valid on most systems (Windows at least).
#
# Replaces the following characters with an underscore (_):
#   <space> \ | / : * ? < >
# ---------------------------------------------------------------------------
def Safe_Filename(filename):
	safe_filename = os.path.basename(filename)
	for char in [' ', "\\", '|', '/', ':', '*', '?', '<', '>']:
		safe_filename = safe_filename.replace(char, '_')
	
	return safe_filename

# ---------------------------------------------------------------------------
# Convert a dotted quad into a long integer. Not sure where I borrowed this
# one from.
# ---------------------------------------------------------------------------
def IP_to_Long(ip):
	longip = 0L
	
	parts = map(int, ip.split('.'))
	for part in parts:
		longip = (longip << 8) + part
	
	return longip

# ---------------------------------------------------------------------------
# Convert a long integer into a dotted quad. This function borrowed from the
# ASPN Python Cookbook.
# ---------------------------------------------------------------------------
def Long_to_IP(longip):
	d = 256 * 256 * 256
	parts = []
	
	while d > 0:
		part, longip = divmod(longip, d)
		parts.append(str(part))
		d /= 256
	
	return '.'.join(parts)

# ---------------------------------------------------------------------------
