# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

'Gets information on video games from various sites.'

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

KLOV_URL = 'http://www.klov.com/results.php?search_desc=0&boolean=AND&q=%s'
MOBYGAMES_URL = 'http://www.mobygames.com/search/quick?q=%s'

# ---------------------------------------------------------------------------

class GameStuff(Plugin):
	_HelpSection = 'games'
	
	def register(self):
		self.addTextEvent(
			method = self.__Fetch_KLOV,
			regexp = r'^klov (?P<title>.+)$',
			help = ('klov', '\02klov\02 <title> : Look up <title> in the Killer List Of Video Games (KLOVG?!)'),
		)
		
		#self.addTextEvent(
		#	method = self.__Fetch_MobyGames,
		#	regexp = re.compile(r'^mobygames (?P<title>.+)$'),
		#	help = ('mobygames', '\02mobygames\02 <title> : Look up <title> at MobyGames.'),
		#)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a KLOV lookup, woo
	def __Fetch_KLOV(self, trigger):
		title = trigger.match.group('title').lower()
		
		if len(title) > 40:
			self.sendReply(trigger, 'Title must be less than 40 characters!')
		
		elif len(title) < 3:
			self.sendReply(trigger, 'Title must be at least 3 characters!')
		
		else:
			url = KLOV_URL % QuoteURL(title)
			self.urlRequest(trigger, self.__Parse_KLOV, url)
	
	# -----------------------------------------------------------------------
	# We got a response from KLOV!
	def __Parse_KLOV(self, trigger, resp):
		title = trigger.match.group('title').lower()
		
		# Nothing, booo
		if resp.data.find('Search Results: 0') >= 0:
			self.sendReply(trigger, 'No matches found.')
		
		# Something!
		else:
			# Find the table we want
			chunk = FindChunk(resp.data, '<HR>', '</TABLE>')
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: table.')
				return
			
			# Find some data rows
			trs = FindChunks(chunk, '<TR BGCOLOR', '<IMG')
			if not trs:
				self.sendReply(trigger, 'Page parsing failed: rows.')
				return
			
			# Get our data out of it
			results = []
			
			for tr in trs:
				game_id = FindChunk(tr, 'game_id=', '">')
				
				tr = tr.replace('</TD>', '</TD>\n')
				lines = StripHTML(tr)
				
				if len(lines) == 4:
					lines.append(game_id)
					results.append(lines)
			
			# See if there are any exact-ish matches
			exacts = [t for t in results if t[0].lower() == title.lower()]
			if exacts:
				results = exacts
			
			# If we just got the 1 result, spit it out
			if len(results) == 1:
				game_name, company, year, game_type, game_id = results[0]
				
				replytext = '(%s) %s [%s] - http://www.klov.com/game_detail.php?game_id=%s' % (company, game_name, year, game_id)
			
			# If we have <= 10 results, spit 'em out
			elif len(results) <= 10:
				parts = []
				for game_name, company, year, game_type, game_id in results:
					part = '(%s) %s [%s]' % (company, game_name, year)
					parts.append(part)
				
				replytext = 'There were \02%d\02 results: %s' % (len(results), ', '.join(parts))
			
			# Too many!
			else:
				url = KLOV_URL % QuoteURL(title)
				
				replytext = 'Too many results returned (%d), try to refine your query! %s' % (len(results), url)
			
			# Spit it out
			self.sendReply(trigger, replytext)
	
	# -----------------------------------------------------------------------
	# Someone wants to do a MobyGames lookup, woo
	def __Fetch_MobyGames(self, trigger):
		title = trigger.match.group('title').lower()
		
		if len(title) > 40:
			self.sendReply(trigger, 'Title must be less than 40 characters!')
		
		elif len(title) < 3:
			self.sendReply(trigger, 'Title must be at least 3 characters!')
		
		else:
			url = MOBYGAMES_URL % QuoteURL(title)
			self.urlRequest(trigger, self.__Parse_MobyGames, url)
	
	# -----------------------------------------------------------------------
	# We got a response from MobyGames!
	def __Parse_MobyGames(self, trigger, resp):
		title = trigger.match.group('title').lower()
		
		# Nothing, booo
		if resp.data.find('came up empty') >= 0:
			self.sendReply(trigger, 'No matches found.')
		
		# Something!
		else:
			# Find the chunk we want
			chunk = FindChunk(resp.data, 'Quick Search', "Not what you're looking for")
			if not chunk:
				self.sendReply(trigger, 'Page parsing failed: data.')
				return
			
			ul = FindChunk(resp.data, '<ul>', '</ul>')
			parts = FindChunks(ul, '<b>', '<td width=25>')
			
			for part in parts:
				print part

# ---------------------------------------------------------------------------
