# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the 'constants' for various parts of Blamehangle.
# ---------------------------------------------------------------------------

BH_VERSION = '0.0.0-CVS'

# ---------------------------------------------------------------------------
# Log constants
# ---------------------------------------------------------------------------

LOG_ALWAYS = 'LOG_ALWAYS'
LOG_DEBUG = 'LOG_DEBUG'
LOG_WARNING = 'LOG_WARNING'

TOLOG_ADMIN_INVALIDPORT = "ERROR: Telnet admin port is privileged or invalid."
TOLOG_ADMIN_PORTINUSE = "ERROR: Telnet admin port is in use."

# ---------------------------------------------------------------------------
# Plugin constants
# ---------------------------------------------------------------------------

PLUGIN_REGISTER = 'PLUGIN_REGISTER'
PLUGIN_TRIGGER = 'PLUGIN_TRIGGER'
PLUGIN_REPLY = 'PLUGIN_REPLY'

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
REQ_CONN = 'REQ_CONN'
REQ_LOG = 'REQ_LOG'
REQ_NOTICE = 'REQ_NOTICE'
REQ_PRIVMSG = 'REQ_PRIVMSG'
REQ_QUERY = 'REQ_QUERY'
REQ_SHUTDOWN = 'REQ_SHUTDOWN'

# ---------------------------------------------------------------------------
# Reply constants
# ---------------------------------------------------------------------------
REPLY_CONN = 'REPLY_CONN'
REPLY_QUERY = 'REPLY_QUERY'
REPLY_TEST = 'REPLY_TEST'
