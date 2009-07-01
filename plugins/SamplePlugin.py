# Copyright (c) 2003-2009, blamehangle team
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

"""
This file demonstrates the structure and basic useful bits of plugins. This
docstring will be used in the automatically generated docs/Plugins.html file.
"""

import re

from classes.Common import *
from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class SamplePlugin(Plugin):
	_HelpSection = 'sample'
	
	# A plugin can define the setup method if it has anything that needs to
	# happen while it is being created. This is called from Plugin's __init__().
	def setup(self):
		# You can omit this method entirely if you don't need it.
		self.rehash()
	
	# A plugin can define the rehash method if it has any config data it needs
	# to deal with. This will be called when the bot is rehashed, but NOT when
	# the plugin is started (hence the self.rehash() call above).
	def rehash(self):
		# Load our config into a useful dictionary
		self.Options = self.OptionsDict('SamplePlugin')
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_once method if it has anything that needs
	# to happen after all plugins and system objects have been created, but
	# before the main loop has been entered.
	def run_once(self):
		# You can omit this method entirely if you don't need it.
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_always method if it has anything that needs
	# to be done during every iteration of the main control loop. This method
	# will be called once per main loop, if defined.
	#
	# NOTE: you really should not need to do this. A TimedEvent is nearly
	#       always the 'right' answer.
	def run_always(self):
		# You can omit this method entirely if you don't need it.
		pass
	
	# -----------------------------------------------------------------------
	# A plugin can define the run_sometimes method if it has anything that needs
	# to be done not that often (currently every 4th main loop iteration, or
	# 0.20s). This method will be called once every 4 main loops, if defined.
	#
	# NOTE: you really should not need to do this. A TimedEvent is nearly
	#       always the 'right' answer.
	def run_always(self):
		# You can omit this method entirely if you don't need it.
		pass
	
	# -----------------------------------------------------------------------
	# Every plugin must define the register method, which is where you register
	# events.
	def register(self):
		# This is a private message + public directed event (the default)
		self.addTextEvent(
			method = self.__Method1,
			regexp = r'^method1$',
			help = ('method1', '\02method1\02 : Our first example method!'),
		)
		# This is a private message event only, and we don't want the regexp
		# to be case-insensitive
		self.addTextEvent(
			method = self.__Method2,
			regexp = re.compile(r'^Method2$'),
			IRCTypes = (IRCT_MSG, IRCT_PUBLIC_D),
			help = ('method2', '\02method2\02 : Our second example method!'),
		)
		# This is a timed event, triggering every 180 (by default) seconds
		self.addTimedEvent(
			method = self.__Method3,
			interval = self.Options['method3_interval'],
			targets = { 'super': ['#test'] },
		)
	
	# -----------------------------------------------------------------------
	# For each event, you need to implement a handler method.
	#
	# 'trigger' is a plugin event trigger, either PluginTextTrigger or
	# PluginTimedTrigger.
	def __Method1(self, trigger):
		# This sends a reply to the person that triggered it, via whichever
		# IRC type it came from.
		self.sendReply(trigger, self.Options['method1_text'])
	
	def __Method2(self, trigger):
		self.sendReply(trigger, self.Options['method2_text'])
	
	# This is a timed trigger, which has it's own "targets" defined. Needs
	# some work to be easier to use :|
	def __Method3(self, trigger):
		replytext = "Wow, %d seconds have passed!" % (trigger.interval)
		self.putlog(LOG_ALWAYS, replytext)
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
