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
	def _message_PLUGIN_REGISTER(self, message):
		raise Error, 'need to overwrite REGISTER message handler in %s' % self.__name
	
	def _message_PLUGIN_TRIGGER(self, message):
		raise Error, 'need to overwrite TRIGGER message handler in %s' % self.__name
