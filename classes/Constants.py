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

PUBLIC = 'IRCT_PUBLIC'
PUBLIC_D = 'IRCT_PUBLIC_D' # public lines directed to the bot, "Blamhangle: blah"
MSG = 'IRCT_MSG'
NOTICE = 'IRCT_NOTICE'
CTCP = 'IRCT_CTCP'
TIMED = 'IRCT_TIMED'

# ---------------------------------------------------------------------------
# Request constants
# ---------------------------------------------------------------------------
REQ_PRIVMSG = 'REQ_PRIVMSG'
REQ_NOTICE = 'REQ_NOTICE'
REQ_LOG = 'REQ_LOG'
