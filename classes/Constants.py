# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Constant values for various things."

BH_VERSION = '0.1.0-CVS'

# ---------------------------------------------------------------------------
# Log constants
# ---------------------------------------------------------------------------

LOG_ALWAYS = 'LOG_ALWAYS'
LOG_DEBUG = 'LOG_DEBUG'
LOG_WARNING = 'LOG_WARNING'
LOG_MSG = 'LOG_MSG'
LOG_QUERY = 'LOG_QUERY'

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
