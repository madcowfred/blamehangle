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
import urllib

from classes.Constants import REPLY_URL

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
def FindChunk(text, start, end, pos=None):
	# Can we find the start?
	if pos is None:
		startpos = text.find(start)
	else:
		startpos = text.find(start, pos)
	
	if startpos < 0:
		return None
	
	startspot = startpos + len(start)
	
	# Can we find the end?
	endpos = text.find(end, startspot)
	if endpos <= startspot:
		return None
	
	# Ok, we have some text now
	chunk = text[startspot:endpos]
	if len(chunk) == 0:
		return None
	
	# Return!
	if pos is None:
		return chunk
	else:
		return (endpos+len(end), chunk)

# As above, but return all matches. Poor man's regexp :)
def FindChunks(text, start, end):
	chunks = []
	n = 0
	
	while 1:
		result = FindChunk(text, start, end, n)
		if result is None:
			return chunks
		else:
			n = result[0]
			chunks.append(result[1])

# ---------------------------------------------------------------------------
# Strip HTML tags from text and split it into non-empty lines
def StripHTML(text):
	# Remove any half tags at the start
	mangled = re.sub(r'^[^<]*?>', '', text)
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
def UnquoteHTML(text, *keep):
	# thing name -> char
	quoted = {
		'lt': '<',
		'gt': '>',
		'amp': '&',
		'quot': '"',
		'nbsp': ' ',
		'ordm': '�',
	}
	
	# don't unquote these
	for k in keep:
		if k in quoted:
			del quoted[k]
	
	# regexp helper function to do the replacement
	def unquote_things(m):
		whole = m.group(0)
		thing = m.group(1).lower()
		# hexadecimal entity
		if thing.startswith('#x'):
			try:
				return chr(int(thing[2:], 16))
			except ValueError:
				return whole
		# decimal entity
		elif thing.startswith('#'):
			try:
				return chr(int(thing[1:]))
			except ValueError:
				return whole
		# named entity
		else:
			return quoted.get(thing, whole)
	
	# go!
	return re.sub(r'&([#A-Za-z0-9]+);', unquote_things, text)

# ---------------------------------------------------------------------------
# urllib stuff
def QuoteURL(url):
	return urllib.quote(url, ':/')

def UnquoteURL(url):
	return urllib.unquote(url).replace(' ', '%20')
