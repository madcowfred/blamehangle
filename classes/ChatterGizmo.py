
from classes import irclib

# ---------------------------------------------------------------------------

class ChatterGizmo:
	"""
	The IRC class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def __init__(self, Config):
		self.__ircobj = irclib.IRC()
		
		self.Config = Config
		
		self.Conns = {}
	
	def main_loop(self):
		print 'main!'
