#!/usr/bin/env python

import socket
import sys

# ---------------------------------------------------------------------------

if len(sys.argv) != 2:
	sys.stdout.write('__FAIL__')
	sys.stdout.flush()
	sys.exit(-1)

host = sys.argv[1]

try:
	results = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
except socket.gaierror:
	sys.stdout.write('__FAIL__')
else:
	for af, socktype, proto, canonname, sa in results:
		if af == socket.AF_INET:
			sys.stdout.write('4 %s\0' % sa[0])
		elif af == socket.AF_INET6:
			sys.stdout.write('6 %s\0' % sa[0])
	
	sys.stdout.write('__END__')

sys.stdout.flush()
