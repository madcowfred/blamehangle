# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Simple clone of asyncore.dispatcher_with_send, without the broken-ness"

import asyncore

class buffered_dispatcher(asyncore.dispatcher):
	def __init__(self, sock=None):
		asyncore.dispatcher.__init__(self, sock)
		self.out_buffer = ''
	
	def add_channel(self, map=None):
		if map is None:
			map = asyncore.socket_map
		map[self._fileno] = self
		# Add ourselves to the poll object
		asyncore.poller.register(self._fileno)
	
	def del_channel(self, map=None):
		if map is None:
			map = asyncore.socket_map
		if map.has_key(self._fileno):
			del map[self._fileno]
		# Remove ourselves from the poll object
		try:
			asyncore.poller.unregister(self._fileno)
		except KeyError:
			pass
	
	# We only want to be writable if we're connecting, or something is in our
	# buffer.
	def writable(self):
		return (not self.connected) or len(self.out_buffer)
	
	# Send some data from our buffer when we can write
	def handle_write(self):
		sent = asyncore.dispatcher.send(self, self.out_buffer)
		self.out_buffer = self.out_buffer[sent:]
	
	# We want buffered output, duh
	def send(self, data):
		self.out_buffer += data
