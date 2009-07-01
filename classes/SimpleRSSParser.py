# Copyright (c) 2003-2009, blamehangle team
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

'Implements a very simple RSS parser. Does not validate the feed.'

import re

from classes.Common import FindChunk, FindChunks, UnquoteHTML

# ---------------------------------------------------------------------------

PARAM_RE = re.compile(r'(\S+)="(.*?)"')

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
		
		enclosure = FindChunk(itemchunk, '<enclosure ', ' />')
		if enclosure is not None:
			item['enclosure'] = dict(PARAM_RE.findall(enclosure))
		
		for thing in 'link', 'desc':
			if item[thing] is not None:
				item[thing] = item[thing].strip()
		
		data['items'].append(item)
	
	# If we didn't find any, cry
	if not data['items']:
		raise Exception, "no valid items found"
	
	return data

# ---------------------------------------------------------------------------
