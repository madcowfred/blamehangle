#!/usr/bin/env python

import getopt
import os
import sys
import time
import gc

from ConfigParser import ConfigParser

#from classes.ChatterGizmo import ChatterGizmo
from classes.Postman import Postman

# ---------------------------------------------------------------------------

def main():
	"The initial setup, config reading, and probably main loop."

	#gc.set_debug(gc.DEBUG_STATS|gc.DEBUG_COLLECTABLE|gc.DEBUG_UNCOLLECTABLE|gc.DEBUG_INSTANCES|gc.DEBUG_OBJECTS)
	# set our own gc thresholds, to keep mem usage from creeping. It seems
	# that the default is extremely slow, and since blamehangle is not an
	# interactive program the minor performance hit taken during garbage
	# collection won't even be noticable.
	#
	# The default is (700, 10, 10) !
	gc.set_threshold(50, 5, 2)
	
	# Parse our command line options
	try:
		opts, args = getopt.getopt(sys.argv[1:], "c:", [ "config=" ])
	
	except getopt.GetoptError:
		Show_Usage()
	
	ConfigFile = None
	for opt, arg in opts:
		if opt in ('-c', '--config'):
			ConfigFile = arg
	
	# Load our config file
	if not ConfigFile or not os.path.exists(ConfigFile):
		Show_Usage()
	
	Config = ConfigParser()
	Config.read(ConfigFile)
	
	# Start up the Postman, and run him forever
	Post = Postman(ConfigFile, Config)
	Post.run_forever()

# ---------------------------------------------------------------------------
	
def Show_Usage():
	print "USAGE: %s [OPTIONS]" % sys.argv[0]
	print
	print " -c, --config=FILE   config file to use"
	print
	
	sys.exit(-1)

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	main()
