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

#from plugins.SamplePlugin import SamplePlugin
from plugins.SmartyPants import SmartyPants
from plugins.Karma import Karma
#from plugins.News import News
from plugins.Calculator import Calculator
from plugins.Airline import Airline
from plugins.MapQuest import MapQuest
from plugins.MoneyMangler import MoneyMangler
from plugins.SportsFan import SportsFan
from plugins.SpellingBee import SpellingBee
