#!/usr/bin/env python

import getopt
import os
import sys

from ConfigParser import ConfigParser

# ---------------------------------------------------------------------------

def main():
	"The initial setup, config reading, and probably main loop."
	
	# Parse our command line options
	try:
		opts, args = getopt.getopt(sys.argv[1:], "bc:", [ "background", "config=" ])
	
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
	
	print Config.sections()

# ---------------------------------------------------------------------------
	
def Show_Usage():
	print "USAGE: %s [OPTIONS]" % argv[0]
	print
	print " -b, --background    run in the background (no screen output)(doesn't work)"
	print " -c, --config=FILE   config file to use"
	print
	
	sys.exit(-1)

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	main()
