# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"""Methods used in more than one place are usually kept here."""

import os
import re
import time
import types
import urllib

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
	#if endpos <= startpos:
	if endpos < 0:
		return None
	
	# Ok, we have some text now
	chunk = text[startspot:endpos]
	
	# Return!
	if pos is None:
		return chunk
	else:
		return (endpos+len(end), chunk)

# As above, but return all matches.
def FindChunks(text, start, end, limit=0):
	chunks = []
	n = 0
	
	while 1:
		result = FindChunk(text, start, end, n)
		if result is None:
			return chunks
		else:
			chunks.append(result[1])
			if limit and len(chunks) == limit:
				return chunks
			n = result[0]

# ---------------------------------------------------------------------------

_half_tags_regexp = re.compile(r'^[^<]*?>')
_html_tags_regexp = re.compile(r'(?s)<.*?>')

# Strip HTML tags from text and split it into non-empty lines
def StripHTML(text):
	# Remove any half tags at the start
	mangled = _half_tags_regexp.sub('', text)
	# Remove all HTML tags
	mangled = _html_tags_regexp.sub('', mangled)
	# Fix escaped bits and pieces
	mangled = UnquoteHTML(mangled)
	# Split into lines that aren't empty
	lines = [s.strip() for s in mangled.splitlines() if s.strip()]
	# Return!
	return lines

# ---------------------------------------------------------------------------
# Replace &blah; quoted things with the actual thing
_unquote_regexp = re.compile(r'&([#A-Za-z0-9]+);')

def UnquoteHTML(text, *keep):
	entities = {
		'lt': '<',
		'gt': '>',
		'amp': '&',
		'quot': '"',
		'nbsp': ' ',
		'ordm': '\xb0',
		'#65295': '/',
	}
	
	# don't unquote these entities
	for k in keep:
		if k in entities:
			del entities[k]
	
	# regexp helper function to do the replacement
	def unquote_things(m):
		whole = m.group(0)
		thing = m.group(1).lower()
		# hexadecimal entity
		if thing.startswith('#x'):
			try:
				return chr(int(thing[2:], 16))
			except ValueError:
				return entities.get(thing, whole)
		# decimal entity
		elif thing.startswith('#'):
			try:
				return chr(int(thing[1:]))
			except ValueError:
				return entities.get(thing, whole)
		# named entity
		else:
			return entities.get(thing, whole)
	
	# go!
	return _unquote_regexp.sub(unquote_things, text)

# ---------------------------------------------------------------------------
# urllib stuff
def QuoteURL(url):
	return urllib.quote(url, ':/')

def UnquoteURL(url):
	return urllib.unquote(url).replace(' ', '%20')
