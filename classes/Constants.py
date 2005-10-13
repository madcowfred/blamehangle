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

"Constant values for various things."

BH_VERSION = '0.1.1'

# ---------------------------------------------------------------------------
# Log constants
# ---------------------------------------------------------------------------

LOG_ALWAYS = 'LOG_ALWAYS'
LOG_DEBUG = 'LOG_DEBUG'
LOG_WARNING = 'LOG_WARNING'
LOG_MSG = 'LOG_MSG'
LOG_QUERY = 'LOG_QUERY'
LOG_EXCEPTION = 'LOG_EXCEPTION'

# ---------------------------------------------------------------------------
# Plugin constants
# ---------------------------------------------------------------------------

PLUGIN_REGISTER = 'PLUGIN_REGISTER'
PLUGIN_UNREGISTER = 'PLUGIN_UNREGISTER'
PLUGIN_DIED = 'PLUGIN_DIED'
PLUGIN_TRIGGER = 'PLUGIN_TRIGGER'
PLUGIN_REPLY = 'PLUGIN_REPLY'
SET_HELP = 'SET_HELP'
UNSET_HELP = 'UNSET_HELP'

# ---------------------------------------------------------------------------
# IRCtype constants
# ---------------------------------------------------------------------------
IRC_EVENT = 'IRC_EVENT'

IRCT_CTCP = 'IRCT_CTCP'
IRCT_CTCP_REPLY = 'IRCT_CTCP_REPLY'
IRCT_PUBLIC = 'IRCT_PUBLIC'
IRCT_PUBLIC_D = 'IRCT_PUBLIC_D'
IRCT_MSG = 'IRCT_MSG'
IRCT_NOTICE = 'IRCT_NOTICE'
IRCT_TIMED = 'IRCT_TIMED'

IRCT_ALL = [IRCT_CTCP, IRCT_CTCP_REPLY, IRCT_PUBLIC, IRCT_PUBLIC_D, IRCT_MSG, IRCT_NOTICE, IRCT_TIMED]

# used by plugins to get raw events, ugh
REQ_IRC_EVENTS = 'REQ_IRC_EVENTS'

# ---------------------------------------------------------------------------
# Request constants
# ---------------------------------------------------------------------------
REQ_DNS = 'REQ_DNS'
REQ_LOG = 'REQ_LOG'
REQ_NOTICE = 'REQ_NOTICE'
REQ_PRIVMSG = 'REQ_PRIVMSG'
REQ_QUERY = 'REQ_QUERY'
REQ_REHASH = 'REQ_REHASH'
REQ_SHUTDOWN = 'REQ_SHUTDOWN'
REQ_URL = 'REQ_URL'
REQ_WRAPS = 'REQ_WRAPS'

GATHER_STATS = 'GATHER_STATS'

# ---------------------------------------------------------------------------
# Reply constants
# ---------------------------------------------------------------------------
REPLY_DNS = 'REPLY_DNS'
REPLY_QUERY = 'REPLY_QUERY'
REPLY_SHUTDOWN = 'REPLY_SHUTDOWN'
REPLY_URL = 'REPLY_URL'
REPLY_WRAPS = 'REPLY_WRAPS'
