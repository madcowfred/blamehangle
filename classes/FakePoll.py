# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Fake poll() for systems that don't implement it (Windows, most notably)."

import select
import socket

# Assume that they need constants
select.POLLIN = 1
select.POLLOUT = 2
select.POLLNVAL = 4

# ---------------------------------------------------------------------------

class FakePoll:
	def __init__(self):
		self.FDs = {}
	
	# Register an FD for polling
	def register(self, fd, flags=None):
		if flags is None:
			self.FDs[fd] = select.POLLIN|select.POLLOUT|select.POLLNVAL
		else:
			self.FDs[fd] = flags
	
	# Unregister an FD
	def unregister(self, fd):
		del self.FDs[fd]
	
	# Poll (select!) for timeout seconds. Nasty.
	def poll(self, timeout):
		fds = self.FDs.keys()
		can_read, can_write = select.select(fds, fds, [], timeout)[:2]
		
		results = {}
		
		for fd in can_read:
			results[fd] = select.POLLIN
		for fd in can_write:
			if fd in results:
				results[fd] |= select.POLLOUT
			else:
				results[fd] = select.POLLOUT
		
		return results.items()

# ---------------------------------------------------------------------------
