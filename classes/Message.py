# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Generic Message class to make message passing easier."

import types

from classes.Constants import REPLY_URL

# ---------------------------------------------------------------------------

class Message:
	def __init__(self, source, targets, ident, data):
		self.source = source
		self.ident = ident
		self.data = data
		
		
		# Do some type checking, since people will feed us all sorts of types
		# of targets.
		t = type(targets)
		
		if t == types.NoneType:
			self.targets = []
			self.targetstring = 'ALL'
		
		elif t in (types.ListType, types.TupleType):
			self.targets = list(targets)
			if targets:
				self.targetstring = ', '.join(targets)
			else:
				self.targetstring = 'ALL'
		
		elif t == types.StringType:
			self.targets = [targets]
			self.targetstring = targets
		
		else:
			print 'WTF? Invalid targets type: %s' % t
	
	# Return a printable string with info about ourself, including
	# how long it's been since we were sent.
	def __str__(self):
		data = repr(self.data)
		#if len(data) >= 100:
		#	data = '<data omitted>'
		if self.ident == REPLY_URL:
			data = '<data omitted>'
		
		return '%s --> %s: (%s) %s' % (self.source, self.targetstring, self.ident, data)

# ---------------------------------------------------------------------------
