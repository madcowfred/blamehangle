#!/usr/bin/env python

import getopt
import os
import sys
import time

from ConfigParser import ConfigParser

from ChatterGizmo import ChatterGizmo

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
	
	# Start up the ChatterGizmo
	Gizmo = ChatterGizmo(Config)
	
	# Shortcut!
	_sleep = time.sleep
	
	while 1:
		Gizmo.run_once()
		_sleep(0.05)

# ---------------------------------------------------------------------------
	
def Show_Usage():
	print "USAGE: %s [OPTIONS]" % sys.argv[0]
	print
	print " -b, --background    run in the background (no screen output)(doesn't work)"
	print " -c, --config=FILE   config file to use"
	print
	
	sys.exit(-1)

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	main()
