#----------------------------------------------------------------------------
# $Id$
#----------------------------------------------------------------------------
# This contains the superclass for all plugins
#
# I'll make this more descriptive when there is actually something to
# describe
#----------------------------------------------------------------------------

from classes.Children import Child

class Plugin(Child):
	def __init__(self, name, outQueue, Config):
		Child.__init__(self, name, outQueue, Config)
		# anything else that needs to be done..
	
	def listEvents(self):
		# This must return a list containing tuples of the form:
		# (IRC_EVENT_TYPE, regexp_to_match, EVENT_TOKEN)
		raise Error, 'need to overwrite Plugin.listEvents in %s' % self.__name
	
	def _handle_PLUGIN_TRIGGER(self, message):
		raise Error, 'need to overwrite message handler in %s' % self.__name
