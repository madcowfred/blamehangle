# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Implements a very simple RSS parser. Does not validate the feed much at all."

from classes.Common import FindChunk, FindChunks, UnquoteHTML

# ---------------------------------------------------------------------------

def SimpleRSSParser(page_text):
	data = { 'feed': {}, 'items': [] }
	
	# See if we can find the channel info
	chunk = FindChunk(page_text, '<channel', '<item>') or \
		FindChunk(page_text, '<channel', '<item ')
	if not chunk:
		raise Exception, "no channel found"
	
	# Get the title
	data['feed']['title'] = FindChunk(page_text, '<title>', '</title>')
	if not data['feed']['title']:
		raise Exception, "no feed title found"
	
	# Find all the items
	items = FindChunks(page_text, '<item>', '</item>') or \
		FindChunks(page_text, '<item ', '</item>')
	if not items:
		raise Exception, "no items found"
	
	for itemchunk in items:
		item = {}
		itemchunk = UnquoteHTML(itemchunk)
		
		item['title'] = FindChunk(itemchunk, '<title>', '</title>')
		if not item['title']:
			continue
		
		item['link'] = FindChunk(itemchunk, '<link>', '</link>') or \
			FindChunk(itemchunk, '<guid>', '</guid>') or None
		
		item['desc'] = FindChunk(itemchunk, '<description>', '</description>') or None
		
		data['items'].append(item)
	
	# If we didn't find any, cry
	if not data['items']:
		raise Exception, "no valid items found"
	
	return data

# ---------------------------------------------------------------------------
