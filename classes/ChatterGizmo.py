
import classes.irclib

# ---------------------------------------------------------------------------

class ChatterGizmo:
	"""
	The IRC class. Does various exciting things, like the multiple IRC
	server handling, and so on.
	"""
	
	def __init__(self):
		self.__ircobj = irclib.IRC()
		
		self.__Connections = {}
