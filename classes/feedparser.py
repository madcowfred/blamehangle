#!/usr/bin/python
"""Ultra-liberal feed parser

Visit http://diveintomark.org/projects/feed_parser/ for the latest version

Handles RSS 0.9x, RSS 1.0, RSS 2.0, Pie/Atom/Echo feeds

RSS 0.9x/common elements:
- title, link, guid, description, webMaster, managingEditor, language
  copyright, lastBuildDate, pubDate

Additional RSS 1.0/2.0 elements:
- dc:rights, dc:language, dc:creator, dc:date, dc:subject,
  content:encoded, admin:generatorAgent, admin:errorReportsTo,
  
Addition Pie/Atom/Echo elements:
- subtitle, created, issued, modified, summary, id, content

Things it handles that choke other parsers:
- bastard combinations of RSS 0.9x and RSS 1.0
- illegal XML characters
- naked and/or invalid HTML in description
- content:encoded in item element
- guid in item element
- fullitem in item element
- non-standard namespaces
- inline XML in content (Pie/Atom/Echo)
- multiple content items per entry (Pie/Atom/Echo)

Requires Python 2.2 or later
"""

__version__ = "2.5.3"
__author__ = "Mark Pilgrim <http://diveintomark.org/>"
__copyright__ = "Copyright 2002-3, Mark Pilgrim"
__contributors__ = ["Jason Diamond <http://injektilo.org/>",
                    "John Beimler <http://john.beimler.org/>"]
__license__ = "Python"
__history__ = """
1.0 - 9/27/2002 - MAP - fixed namespace processing on prefixed RSS 2.0 elements,
  added Simon Fell's test suite
1.1 - 9/29/2002 - MAP - fixed infinite loop on incomplete CDATA sections
2.0 - 10/19/2002
  JD - use inchannel to watch out for image and textinput elements which can
  also contain title, link, and description elements
  JD - check for isPermaLink="false" attribute on guid elements
  JD - replaced openAnything with open_resource supporting ETag and
  If-Modified-Since request headers
  JD - parse now accepts etag, modified, agent, and referrer optional
  arguments
  JD - modified parse to return a dictionary instead of a tuple so that any
  etag or modified information can be returned and cached by the caller
2.0.1 - 10/21/2002 - MAP - changed parse() so that if we don't get anything
  because of etag/modified, return the old etag/modified to the caller to
  indicate why nothing is being returned
2.0.2 - 10/21/2002 - JB - added the inchannel to the if statement, otherwise its
  useless.  Fixes the problem JD was addressing by adding it.
2.1 - 11/14/2002 - MAP - added gzip support
2.2 - 1/27/2003 - MAP - added attribute support, admin:generatorAgent.
  start_admingeneratoragent is an example of how to handle elements with
  only attributes, no content.
2.3 - 6/11/2003 - MAP - added USER_AGENT for default (if caller doesn't specify);
  also, make sure we send the User-Agent even if urllib2 isn't available.
  Match any variation of backend.userland.com/rss namespace.
2.3.1 - 6/12/2003 - MAP - if item has both link and guid, return both as-is.
2.4 - 7/9/2003 - MAP - added preliminary Pie/Atom/Echo support based on Sam Ruby's
  snapshot of July 1 <http://www.intertwingly.net/blog/1506.html>; changed
  project name
2.5 - 7/25/2003 - MAP - changed to Python license (all contributors agree);
  removed unnecessary urllib code -- urllib2 should always be available anyway;
  return actual url, status, and full HTTP headers (as result['url'],
  result['status'], and result['headers']) if parsing a remote feed over HTTP --
  this should pass all the HTTP tests at <http://diveintomark.org/tests/client/http/>;
  added the latest namespace-of-the-week for RSS 2.0
2.5.1 - 7/26/2003 - RMK - clear opener.addheaders so we only send our custom
  User-Agent (otherwise urllib2 sends two, which confuses some servers)
2.5.2 - 7/28/2003 - MAP - entity-decode inline xml properly; added support for
  inline <xhtml:body> and <xhtml:div> as used in some RSS 2.0 feeds
2.5.3 - 8/6/2003 - TvdV - patch to track whether we're inside an image or
  textInput, and also to return the character encoding (if specified)
"""

import cgi, re, sgmllib, string
sgmllib.tagfind = re.compile('[a-zA-Z][-_.:a-zA-Z0-9]*')

USER_AGENT = "UltraLiberalFeedParser/%s +http://diveintomark.org/projects/feed_parser/" % __version__

def decodeEntities(data):
    data = data or ''
    data = data.replace('&lt;', '<')
    data = data.replace('&gt;', '>')
    data = data.replace('&quot;', '"')
    data = data.replace('&apos;', "'")
    data = data.replace('&amp;', '&')
    return data

class FeedParser(sgmllib.SGMLParser):
    namespaces = {"http://backend.userland.com/rss": "",
                  "http://blogs.law.harvard.edu/tech/rss": "",
                  "http://purl.org/rss/1.0/": "",
                  "http://example.com/newformat#": "",
                  "http://example.com/necho": "",
                  "http://purl.org/echo/": "",
                  "uri/of/echo/namespace#": "",
                  "http://purl.org/pie/": "",
                  "http://purl.org/rss/1.0/modules/textinput/": "ti",
                  "http://purl.org/rss/1.0/modules/company/": "co",
                  "http://purl.org/rss/1.0/modules/syndication/": "sy",
                  "http://purl.org/dc/elements/1.1/": "dc",
                  "http://webns.net/mvcb/": "admin",
                  "http://www.w3.org/1999/xhtml": "xhtml"}

    def reset(self):
        self.channel = {}
        self.items = []
        self.elementstack = []
        self.inchannel = 0
        self.initem = 0
        self.incontent = 0
        self.intextinput = 0
        self.inimage = 0
        self.contentmode = None
        self.contenttype = None
        self.contentlang = None
        self.namespacemap = {}
        sgmllib.SGMLParser.reset(self)

    def push(self, element, expectingText):
        self.elementstack.append([element, expectingText, []])

    def pop(self, element):
        if not self.elementstack: return
        if self.elementstack[-1][0] != element: return
        element, expectingText, pieces = self.elementstack.pop()
        if not expectingText: return
        output = "".join(pieces)
        output = decodeEntities(output)
        if self.incontent and self.initem:
            if not self.items[-1].has_key(element):
                self.items[-1][element] = []
            self.items[-1][element].append({"language":self.contentlang, "type":self.contenttype, "value":output})
        elif self.initem:
            self.items[-1][element] = output
        elif self.inchannel and (not self.intextinput) and (not self.inimage):
            self.channel[element] = output

    def _addNamespaces(self, attrs):
        for prefix, value in attrs:
            if not prefix.startswith("xmlns:"): continue
            prefix = prefix[6:]
            if prefix.find('backend.userland.com/rss') <> -1:
                # match any backend.userland.com namespace
                prefix = 'http://backend.userland.com/rss'
            if self.namespaces.has_key(value):
                self.namespacemap[prefix] = self.namespaces[value]

    def _mapToStandardPrefix(self, name):
        colonpos = name.find(':')
        if colonpos <> -1:
            prefix = name[:colonpos]
            suffix = name[colonpos+1:]
            prefix = self.namespacemap.get(prefix, prefix)
            name = prefix + ':' + suffix
        return name
        
    def _getAttribute(self, attrs, name):
        value = [v for k, v in attrs if self._mapToStandardPrefix(k) == name]
        if value:
            value = value[0]
        else:
            value = None
        return value
            
    def start_channel(self, attrs):
        self.push('channel', 0)
        self.inchannel = 1

    def end_channel(self):
        self.pop('channel')
        self.inchannel = 0
    
    def start_image(self, attrs):
        self.inimage = 1
            
    def end_image(self):
        self.inimage = 0
                
    def start_textinput(self, attrs):
        self.intextinput = 1
        
    def end_textinput(self):
        self.intextinput = 0

    def start_item(self, attrs):
        self.items.append({})
        self.push('item', 0)
        self.initem = 1

    def end_item(self):
        self.pop('item')
        self.initem = 0

    def start_dc_language(self, attrs):
        self.push('language', 1)
    start_language = start_dc_language

    def end_dc_language(self):
        self.pop('language')
    end_language = end_dc_language

    def start_dc_creator(self, attrs):
        self.push('creator', 1)
    start_managingeditor = start_dc_creator
    start_webmaster = start_dc_creator

    def end_dc_creator(self):
        self.pop('creator')
    end_managingeditor = end_dc_creator
    end_webmaster = end_dc_creator

    def start_dc_rights(self, attrs):
        self.push('rights', 1)
    start_copyright = start_dc_rights

    def end_dc_rights(self):
        self.pop('rights')
    end_copyright = end_dc_rights

    def start_dc_date(self, attrs):
        self.push('date', 1)
    start_lastbuilddate = start_dc_date
    start_pubdate = start_dc_date

    def end_dc_date(self):
        self.pop('date')
    end_lastbuilddate = end_dc_date
    end_pubdate = end_dc_date

    def start_dc_subject(self, attrs):
        self.push('category', 1)

    def end_dc_subject(self):
        self.pop('category')

    def start_link(self, attrs):
        self.push('link', self.inchannel or self.initem)

    def end_link(self):
        self.pop('link')

    def start_guid(self, attrs):
        self.guidislink = ('ispermalink', 'false') not in attrs
        self.push('guid', 1)

    def end_guid(self):
        self.pop('guid')
        if self.guidislink:
            if not self.items[-1].has_key('link'):
                # guid acts as link, but only if "ispermalink" is not present or is "true",
                # and only if the item doesn't already have a link element
                self.items[-1]['link'] = self.items[-1]['guid']

    def start_title(self, attrs):
        self.push('title', self.inchannel or self.initem)

    def start_description(self, attrs):
        self.push('description', self.inchannel or self.initem)

    def start_content_encoded(self, attrs):
        self.push('content_encoded', 1)
    start_fullitem = start_content_encoded

    def end_content_encoded(self):
        self.pop('content_encoded')
    end_fullitem = end_content_encoded

    def start_admin_generatoragent(self, attrs):
        self.push('generator', 1)
        value = self._getAttribute(attrs, 'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop('generator')

    def start_feed(self, attrs):
        self.inchannel = 1

    def end_feed(self):
        self.inchannel = 0

    def start_entry(self, attrs):
        self.items.append({})
        self.push('item', 0)
        self.initem = 1

    def end_entry(self):
        self.pop('item')
        self.initem = 0
        
    def start_subtitle(self, attrs):
        self.push('subtitle', 1)

    def end_subtitle(self):
        self.pop('subtitle')

    def start_summary(self, attrs):
        self.push('summary', 1)

    def end_summary(self):
        self.pop('summary')
        
    def start_modified(self, attrs):
        self.push('modified', 1)

    def end_modified(self):
        self.pop('modified')

    def start_created(self, attrs):
        self.push('created', 1)

    def end_created(self):
        self.pop('created')

    def start_issued(self, attrs):
        self.push('issued', 1)

    def end_issued(self):
        self.pop('issued')

    def start_id(self, attrs):
        self.push('id', 1)

    def end_id(self):
        self.pop('id')

    def start_content(self, attrs):
        self.incontent = 1
        if ('mode', 'escaped') in attrs:
            self.contentmode = 'escaped'
        elif ('mode', 'base64') in attrs:
            self.contentmode = 'base64'
        else:
            self.contentmode = 'xml'
        mimetype = [v for k, v in attrs if k=='type']
        if mimetype:
            self.contenttype = mimetype[0]
        xmllang = [v for k, v in attrs if k=='xml:lang']
        if xmllang:
            self.contentlang = xmllang[0]
        self.push('content', 1)

    def end_content(self):
        self.pop('content')
        self.incontent = 0
        self.contentmode = None
        self.contenttype = None
        self.contentlang = None

    def start_body(self, attrs):
        self.incontent = 1
        self.contentmode = 'xml'
        self.contenttype = 'application/xhtml+xml'
        xmllang = [v for k, v in attrs if k=='xml:lang']
        if xmllang:
            self.contentlang = xmllang[0]
        self.push('content', 1)

    start_div = start_body
    start_xhtml_body = start_body
    start_xhtml_div = start_body
    end_body = end_content
    end_div = end_content
    end_xhtml_body = end_content
    end_xhtml_div = end_content
        
    def unknown_starttag(self, tag, attrs):
        if self.incontent and self.contentmode == 'xml':
            self.handle_data("<%s%s>" % (tag, "".join([' %s="%s"' % t for t in attrs])))
            return
        self._addNamespaces(attrs)
        colonpos = tag.find(':')
        if colonpos <> -1:
            prefix = tag[:colonpos]
            suffix = tag[colonpos+1:]
            prefix = self.namespacemap.get(prefix, prefix)
            if prefix:
                prefix = prefix + '_'
            methodname = 'start_' + prefix + suffix
            try:
                method = getattr(self, methodname)
                return method(attrs)
            except AttributeError:
                return self.push(prefix + suffix, 0)
        return self.push(tag, 0)

    def unknown_endtag(self, tag):
        if self.incontent and self.contentmode == 'xml':
            self.handle_data("</%s>" % tag)
            return
        colonpos = tag.find(':')
        if colonpos <> -1:
            prefix = tag[:colonpos]
            suffix = tag[colonpos+1:]
            prefix = self.namespacemap.get(prefix, prefix)
            if prefix:
                prefix = prefix + '_'
            methodname = 'end_' + prefix + suffix
            try:
                method = getattr(self, methodname)
                return method()
            except AttributeError:
                return self.pop(prefix + suffix)
        return self.pop(tag)

    def handle_charref(self, ref):
        # called for each character reference, e.g. for "&#160;", ref will be "160"
        # Reconstruct the original character reference.
        if not self.elementstack: return
        text = "&#%s;" % ref
        if self.incontent and self.contentmode == 'xml':
            text = cgi.escape(text)
        self.elementstack[-1][2].append(text)

    def handle_entityref(self, ref):
        # called for each entity reference, e.g. for "&copy;", ref will be "copy"
        # Reconstruct the original entity reference.
        if not self.elementstack: return
        text = "&%s;" % ref
        if self.incontent and self.contentmode == 'xml':
            text = cgi.escape(text)
        self.elementstack[-1][2].append(text)

    def handle_data(self, text):
        # called for each block of plain text, i.e. outside of any tag and
        # not containing any character or entity references
        if not self.elementstack: return
        if self.incontent and self.contentmode == 'xml':
            text = cgi.escape(text)
        self.elementstack[-1][2].append(text)

    def handle_comment(self, text):
        # called for each comment, e.g. <!-- insert message here -->
        pass

    def handle_pi(self, text):
        # called for each processing instruction, e.g. <?instruction>
        pass

    def handle_decl(self, text):
        # called for the DOCTYPE, if present, e.g.
        # <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        #     "http://www.w3.org/TR/html4/loose.dtd">
        pass

    _new_declname_match = re.compile(r'[a-zA-Z][-_.a-zA-Z0-9:]*\s*').match
    def _scan_name(self, i, declstartpos):
        rawdata = self.rawdata
        n = len(rawdata)
        if i == n:
            return None, -1
        m = self._new_declname_match(rawdata, i)
        if m:
            s = m.group()
            name = s.strip()
            if (i + len(s)) == n:
                return None, -1  # end of buffer
            return string.lower(name), m.end()
        else:
            self.updatepos(declstartpos, i)
            self.error("expected name token")

    def parse_declaration(self, i):
        # override internal declaration handler to handle CDATA blocks
        if self.rawdata[i:i+9] == '<![CDATA[':
            k = self.rawdata.find(']]>', i)
            if k == -1: k = len(self.rawdata)
            self.handle_data(cgi.escape(self.rawdata[i+9:k]))
            return k+3
        return sgmllib.SGMLParser.parse_declaration(self, i)
