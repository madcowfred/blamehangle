# -*- coding: iso-8859-1 -*-
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains classes and constants used in most (or all)
# of the other files.
# ---------------------------------------------------------------------------

import os
import re
import time
import types

from classes.Constants import REPLY_URL

# ---------------------------------------------------------------------------
# An empty class!
class EmptyClass:
	pass

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
			self.targets = list(targets)
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
		data = repr(self.data)
		#if len(data) >= 100:
		#	data = '<data omitted>'
		if self.ident == REPLY_URL:
			data = '<data omitted>'
		
		return '%s --> %s: (%s) %s' % (self.source, self.targetstring, self.ident, data)

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

# Sort out the wacky timezone into something we can use
def GetTZ():
	# Use DST if it's there
	if time.daylight:
		tz = time.altzone
	else:
		tz = time.timezone
	
	# GMT people
	if tz == 0 or tz == -0:
		return '+0000'
	
	# These people are actually ahead
	if tz < 0:
		sign = '+'
		tz = tz - tz - tz
	else:
		sign = '-'
	
	# Construct the time zone
	hours, mins = divmod(tz / 60, 60)
	return '%s%02d%02d' % (sign, hours, mins)

# ---------------------------------------------------------------------------
# Search through text, finding the chunk between start and end.
def FindChunk(text, start, end):
	# Can we find the start?
	startpos = text.find(start)
	if startpos < 0:
		return None
	
	# Can we find the end?
	endpos = text.find(end, startpos)
	if endpos <= startpos:
		return None
	
	# No (or null range) text?
	startspot = startpos + len(start)
	if endpos <= startspot:
		return None
	
	# Ok, we have some text now
	chunk = text[startspot:endpos]
	if len(chunk) == 0:
		return None
	
	# Return!
	return chunk

# ---------------------------------------------------------------------------
# Strip HTML tags from text and split it into non-empty lines
def StripHTML(text):
	# Remove any half tags at the start
	mangled = re.sub(r'^[^<]+>', '', text)
	# Remove all HTML tags
	mangled = re.sub(r'(?s)<.*?>', '', mangled)
	# Fix escaped bits and pieces
	mangled = UnquoteHTML(mangled)
	# Split into lines that aren't empty
	lines = [s.strip() for s in mangled.splitlines() if s.strip()]
	# Return!
	return lines

# ---------------------------------------------------------------------------
# Replace &blah; quoted things with the actual thing
def UnquoteHTML(text):
	# thing name -> char
	quoted = {
		'amp': '&',
		'nbsp': ' ',
		'ordm': '°',
		'quot': '"',
	}
	
	# regexp helper function to do the replacement
	def unquote_things(m):
		whole = m.group(0)
		thing = m.group(1).lower()
		if thing.startswith('#'):
			try:
				return chr(int(thing[1:]))
			except ValueError:
				return whole
		else:
			return quoted.get(thing, whole)
	
	# go!
	return re.sub(r'\&([^;]+);', unquote_things, text)

