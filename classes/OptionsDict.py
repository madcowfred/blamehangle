# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Simple class to add some helpful functions to our options dictionaries."

class OptionsDict(dict):
	def get_net(self, option, trigger, chan=None):
		network = trigger.conn.options['name'].lower()
		if chan is None:
			return self.get(option, {}).get(network, None)
		else:
			return self.get(option, {}).get(network, {}).get(chan.lower(), None)
