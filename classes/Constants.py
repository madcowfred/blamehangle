# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the 'constants' for various parts of Blamehangle.
# ---------------------------------------------------------------------------

BH_VERSION = '0.1.0-CVS'

# ---------------------------------------------------------------------------
# Log constants
# ---------------------------------------------------------------------------

LOG_ALWAYS = 'LOG_ALWAYS'
LOG_DEBUG = 'LOG_DEBUG'
LOG_WARNING = 'LOG_WARNING'
LOG_MSG = 'LOG_MSG'

TOLOG_ADMIN_INVALIDPORT = "ERROR: Telnet admin port is privileged or invalid."
TOLOG_ADMIN_PORTINUSE = "ERROR: Telnet admin port is in use."

# ---------------------------------------------------------------------------
# Plugin constants
# ---------------------------------------------------------------------------

PLUGIN_REGISTER = 'PLUGIN_REGISTER'
PLUGIN_TRIGGER = 'PLUGIN_TRIGGER'
PLUGIN_REPLY = 'PLUGIN_REPLY'
SET_HELP = 'SET_HELP'

# ---------------------------------------------------------------------------
# IRCtype constants
# ---------------------------------------------------------------------------
IRC_EVENT = 'IRC_EVENT'

IRCT_PUBLIC = 'IRCT_PUBLIC'
IRCT_PUBLIC_D = 'IRCT_PUBLIC_D'
IRCT_MSG = 'IRCT_MSG'
IRCT_NOTICE = 'IRCT_NOTICE'
IRCT_CTCP = 'IRCT_CTCP'
IRCT_TIMED = 'IRCT_TIMED'

# ---------------------------------------------------------------------------
# Request constants
# ---------------------------------------------------------------------------
REQ_ADD_TIMER = 'REQ_ADD_TIMER'
REQ_DEL_TIMER = 'REQ_DEL_TIMER'
REQ_LOG = 'REQ_LOG'
REQ_NOTICE = 'REQ_NOTICE'
REQ_PRIVMSG = 'REQ_PRIVMSG'
REQ_QUERY = 'REQ_QUERY'
REQ_SHUTDOWN = 'REQ_SHUTDOWN'
REQ_URL = 'REQ_URL'

REQ_LOAD_CONFIG = 'REQ_LOAD_CONFIG'
REQ_REHASH = 'REQ_REHASH'

# ---------------------------------------------------------------------------
# Reply constants
# ---------------------------------------------------------------------------
REPLY_QUERY = 'REPLY_QUERY'
REPLY_TIMER_TRIGGER = 'REPLY_TIMER_TRIGGER'
REPLY_URL = 'REPLY_URL'
REPLY_SHUTDOWN = 'REPLY_SHUTDOWN'
