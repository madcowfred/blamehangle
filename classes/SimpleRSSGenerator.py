# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Implements a very simple RSS feed generator."

import time

from classes.Constants import LOG_DEBUG, LOG_WARNING

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
		
		line = '<title>%s</title>' % (item['title'])
		lines.append(line)
		
		if 'link' in item:
			line = '<link>%s</link>' % (item['link'])
			lines.append(line)
		
		if 'pubdate' in item:
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
