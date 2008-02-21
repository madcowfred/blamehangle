# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2003-2008, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"Implements a very simple RSS feed generator."

import re
import time

from classes.Constants import LOG_DEBUG, LOG_WARNING

# ---------------------------------------------------------------------------
# ARGH!
ENTITY_RE = re.compile(r'&(?![a-z]{1,4};)')

# ---------------------------------------------------------------------------

def SimpleRSSGenerator(filename, feedinfo, items, putlog=None):
	started = time.time()
	
	try:
		rssfile = open(filename, 'w')
	except Exception, msg:
		if putlog is not None:
			tolog = "Error opening '%s' for writing: %s" % (filename, msg)
			putlog(LOG_WARNING, tolog)
		return
	
	feedinfo['builddate'] = ISODate(time.gmtime())
	
	# RSS header
	print >>rssfile, """<?xml version="1.0" encoding="iso-8859-1"?>
<rss version="2.0">
<channel>
<title>%(title)s</title>
<link>%(link)s</link>
<description>%(description)s</description>
<language>en-us</language>
<lastBuildDate>%(builddate)s</lastBuildDate>
<generator>blamehangle SimpleRSSGenerator</generator>
<ttl>%(ttl)s</ttl>""" % (feedinfo)
	
	# Items!
	for item in items:
		lines = []
		
		lines.append('<item>')
		
		line = '<title>%s</title>' % (ENTITY_RE.sub('&amp;', item['title']))
		lines.append(line)
		
		if item.get('link', None) is not None:
			line = '<link>%s</link>' % (ENTITY_RE.sub('&amp;', item['link']))
			lines.append(line)
		
		if item.get('description', None) is not None:
			line = '<description>%s</description>' % (ENTITY_RE.sub('&amp;', item['description']))
			lines.append(line)
		
		if item.get('pubdate', None) is not None:
			line = '<pubDate>%s</pubDate>' % (ISODate(item['pubdate']))
			lines.append(line)
		
		lines.append('</item>')
		
		print >>rssfile, '\n'.join(lines)
	
	# RSS footer
	print >>rssfile, """</channel>
</rss>"""
		
	rssfile.close()
	
	# Done
	if putlog is not None:
		tolog = "RSS feed '%s' generated in %0.2fs" % (feedinfo['title'], time.time() - started)
		putlog(LOG_DEBUG, tolog)

# ---------------------------------------------------------------------------

def ISODate(t):
	return time.strftime("%a, %d %b %Y %H:%M:%S GMT", t)

# ---------------------------------------------------------------------------
