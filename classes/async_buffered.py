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

"Simple clone of asyncore.dispatcher_with_send, without the broken-ness"

import asyncore
import select

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
		
		# Remove ourselves from the async map
		try:
			if map.has_key(self._fileno):
				del map[self._fileno]
		except AttributeError:
			return
		
		# Remove ourselves from the poll object
		try:
			asyncore.poller.unregister(self._fileno)
		except KeyError:
			pass
	
	def close(self):
		self.del_channel()
		if self.socket is not None:
			self.socket.close()
	
	# We only want to be writable if we're connecting, or something is in our
	# buffer.
	def writable(self):
		return (not self.connected) or len(self.out_buffer)
	
	# Send some data from our buffer when we can write
	def handle_write(self):
		#print '%d wants to write!' % self._fileno
		
		if not self.writable():
			# We don't have any buffer, silly thing
			#print '%d has no data!' % self._fileno
			asyncore.poller.register(self._fileno, select.POLLIN)
			return
		
		sent = asyncore.dispatcher.send(self, self.out_buffer)
		self.out_buffer = self.out_buffer[sent:]
	
	# We want buffered output, duh
	def send(self, data):
		self.out_buffer += data
		# We need to know about writable things now
		asyncore.poller.register(self._fileno)
		#print '%d has data!' % self._fileno
