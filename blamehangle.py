#!/usr/bin/env python

import getopt
import os
import sys
import time

from ConfigParser import ConfigParser

#from classes.ChatterGizmo import ChatterGizmo
from classes.Postman import Postman

# ---------------------------------------------------------------------------

def main():
	"The initial setup, config reading, and probably main loop."
	
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
