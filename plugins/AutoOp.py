# Copyright (c) 2003-2012, blamehangle team
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
Automatically op matching hostmasks when they join a channel. This tends to
be a _really bad idea_.
"""

from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class AutoOp(Plugin):
    def setup(self):
        self.rehash()
    
    def rehash(self):
        self.Options = self.OptionsDict('AutoOp', autosplit=True)
    
    def register(self):
        self.sendMessage('ChatterGizmo', REQ_IRC_EVENTS, ['join'])
    
    # -----------------------------------------------------------------------
    
    def _message_IRC_EVENT(self, message):
        wrap, event, args = message.data
        
        if event.command == 'join':
            chan, ui = args
            network = wrap.name.lower()
            
            if network not in self.Options['chans'] or chan not in self.Options['chans'][network]:
                return
            if ui is None:
                return
            if not self.Userlist.Has_Flag(ui, 'AutoOp', 'autoop'):
                return
            
            command = 'MODE %s +o %s' % (chan, ui.nick)
            wrap.sendline(command)
            
            tolog = 'Automatically opped %s on %s' % (ui.nick, chan)
            self.connlog(self.logger.info, wrap, tolog)
