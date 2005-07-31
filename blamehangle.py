#!/usr/bin/env python
# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Copyright (c) 2004-2005, blamehangle team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import gc
import getopt
import os
import sys
import time

from ConfigParser import ConfigParser

from classes.Postman import Postman

# ---------------------------------------------------------------------------
# We only want Python 2.3 or above people, sorry
if sys.version_info[:2] < (2, 3):
	print "ERROR: blamehangle requires Python 2.3 or later!"
	sys.exit(1)

# ---------------------------------------------------------------------------

def main():
	"""
	The initial setup for blamehangle. Parse command line options, read config
	file, and start the Postman.
	"""
	
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
		opts, args = getopt.getopt(sys.argv[1:], 'c:p', [ 'config=', 'profile' ])
	except getopt.GetoptError:
		Show_Usage()
	
	ConfigFile = None
	Profiled = 0
	for opt, arg in opts:
		if opt in ('-c', '--config'):
			ConfigFile = arg
		if opt in ('-p', '--profile'):
			Profiled = 1
	
	# Load our config file
	if not ConfigFile or not os.path.exists(ConfigFile):
		Show_Usage()
	
	Config = ConfigParser()
	Config.read(ConfigFile)
	
	# Start up the Postman, and run him forever. If we're profiling, do that.
	Post = Postman(ConfigFile, Config)
	
	if Profiled:
		import hotshot
		prof = hotshot.Profile('hangle.prof')
		prof.runcall(Post.run_forever)
		prof.close()
		
		# Print some profile stats
		import hotshot.stats
		stats = hotshot.stats.load('hangle.prof')
		stats.strip_dirs()
		stats.sort_stats('time', 'calls')
		stats.print_stats(25)
	
	else:
		Post.run_forever()

# ---------------------------------------------------------------------------
	
def Show_Usage():
	print "USAGE: %s [OPTIONS]" % sys.argv[0]
	print
	print " -c, --config=FILE   config file to use"
	print " -p, --profile       run with the profiler active, saves to 'profile.data'"
	print
	
	sys.exit(-1)

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	main()
