#----------------------------------------------------------------------------#
# $Id#
#----------------------------------------------------------------------------#
# This file is the outermost wrapper for the plugin interface.
#
# To add a plugin to Blamehangle, add an import statement for it below.
#----------------------------------------------------------------------------#

#----------------------------------------------------------------------------#
# Put your plugins here
#----------------------------------------------------------------------------#

from plugins.Karma import Karma













#----------------------------------------------------------------------------#
# DO NOT EDIT BELOW THIS POINT
#----------------------------------------------------------------------------#

# system "plugins" that are non-optional


#----------------------------------------------------------------------------#

#import types
#
#from classes.Plugin import Plugin
#
## A somewhat ugly hack that will generate the list of all Plugins. The
## motivation for this is that to "install" a plugin all you need to do is
## add it to the import list at the top of this file, instead of having to
## also find a list of all plugins and add it there also.
#def PluginList():
#	plugin_list = []
#	for name in dir(Plugins):
#			obj = getattr(Plugins, name)
#			if type(obj) == types.ClassType:
#				if issubclass(obj, Plugin):
#					plugin_list.append(name)
#	
#	return plugin_list
#
##----------------------------------------------------------------------------#
