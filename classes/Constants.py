# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This file contains the 'constants' for various parts of MadCowOffer.
# ---------------------------------------------------------------------------

MCO_VERSION = '0.4.0-CVS'

# ---------------------------------------------------------------------------
# Log constants
# ---------------------------------------------------------------------------
LOG_ALWAYS = 'LOG_ALWAYS'
LOG_DEBUG = 'LOG_DEBUG'
LOG_WARNING = 'LOG_WARNING'

TOLOG_ADMIN_INVALIDPORT = "ERROR: Telnet admin port is privileged or invalid."
TOLOG_ADMIN_PORTINUSE = "ERROR: Telnet admin port is in use."

# ---------------------------------------------------------------------------
# Request constants
# ---------------------------------------------------------------------------
REQ_ADVERT_DATA = 'REQ_ADVERT_DATA'
REQ_DCC_UPLOAD = 'REQ_DCC_UPLOAD'
REQ_IGNORE_ADD = 'REQ_IGNORE_ADD'
REQ_IGNORE_REMOVE = 'REQ_IGNORE_REMOVE'
REQ_JOIN_NOW = 'REQ_JOIN_NOW'
REQ_KILL_TRANSFER = 'REQ_KILL_TRANSFER'
REQ_LOAD_CONFIG = 'REQ_LOAD_CONFIG'
REQ_LOAD_PACKS = 'REQ_LOAD_PACKS'
REQ_LIST_IGNORES = 'REQ_LIST_IGNORES'
REQ_LIST_TRANSFERS = 'REQ_LIST_TRANSFERS'
REQ_LOG = 'REQ_LOG'
REQ_PRIVMSG = 'REQ_PRIVMSG'
REQ_NOTICE = 'REQ_NOTICE'
REQ_PACKNUM_OK = 'REQ_PACKNUM_OK'
REQ_REHASH = 'REQ_REHASH'
REQ_RESUME = 'REQ_RESUME'
REQ_SEARCH = 'REQ_SEARCH'
REQ_SEND_INDEX = 'REQ_SEND_INDEX'
REQ_SEND_PACK = 'REQ_SEND_PACK'
REQ_SHUTDOWN = 'REQ_SHUTDOWN'
REQ_USER_KILL = 'REQ_USER_KILL'
BAD_PACK = 'BAD_PACK'
DELAYED_MSG = 'DELAYED_MSG'
XDCC_QCHECK = 'XDCC_QCHECK'

# ---------------------------------------------------------------------------
# Reply constants
# ---------------------------------------------------------------------------
REPLY_ADVERT_DATA = 'REPLY_ADVERT_DATA'
REPLY_IGNORE_ADD_OK = 'REPLY_IGNORE_ADD_OK'
REPLY_IGNORE_ADD_FAIL = 'REPLY_IGNORE_ADD_FAIL'
REPLY_IGNORE_REMOVE_OK = 'REPLY_IGNORE_REMOVE_OK'
REPLY_IGNORE_REMOVE_FAIL = 'REPLY_IGNORE_REMOVE_FAIL'
REPLY_IGNORE_DATA = 'REPLY_IGNORE_DATA'
REPLY_INDEX_DATA = 'REPLY_INDEX_DATA'
REPLY_JOIN_NOW = 'REPLY_JOIN_NOW'
REPLY_LIST_IGNORES = 'REPLY_LIST_IGNORES'
REPLY_LIST_TRANSFERS = 'REPLY_LIST_TRANSFERS'
REPLY_LOAD_CONFIG = 'REPLY_LOAD_CONFIG'
REPLY_LOAD_PACKS = 'REPLY_LOAD_PACKS'
REPLY_LOCALADDR = 'REPLY_LOCALADDR'
REPLY_NONE = 'REPLY_NONE'
REPLY_PACK = 'REPLY_PACK'
REPLY_PACK_DATA = 'REPLY_PACK_DATA'
REPLY_PACKNUM_BAD = 'REPLY_PACKNUM_BAD'
REPLY_PACKNUM_OK = 'REPLY_PACKNUM_OK'
REPLY_SEARCH = 'REPLY_SEARCH'
REPLY_TOTALS_DATA = 'REPLY_TOTALS_DATA'
REPLY_TRANSFER_KILL_OK = 'REPLY_TRANSFER_KILL_OK'
REPLY_TRANSFER_KILL_FAIL = 'REPLY_TRANSFER_KILL_FAIL'

# ---------------------------------------------------------------------------
# Completed transfer constants
# ---------------------------------------------------------------------------
SEND_DONE = 'SEND_DONE'

# ---------------------------------------------------------------------------
# XDCC Queue constants
# ---------------------------------------------------------------------------
DEAD_ITEM = 'DEAD_ITEM'
USER_RECOVER = 'USER_RECOVER'
USER_SPOT = 'USER_SPOT'
USER_MYQUEUE = 'USER_MYQUEUE'
USER_REMOVEME = 'USER_REMOVEME'
USER_DELETE = 'USER_DELETE'
USE_SLOT = 'USE_SLOT'
DONT_USE_SLOT = 'DONT_USE_SLOT'
XDCC_STATUS = 'XDCC_STATUS'

# ---------------------------------------------------------------------------
# IRC Event constants
# ---------------------------------------------------------------------------
NICK_CHANGE = 'NICK_CHANGE'
USER_LEFT = 'USER_LEFT'

# ---------------------------------------------------------------------------
# DCC status constants
# ---------------------------------------------------------------------------
DCC_STATUS_STARTING = 'Starting'
DCC_STATUS_LISTENING = 'Listening'
DCC_STATUS_CONNECTING = 'Connecting'
DCC_STATUS_ACTIVE = 'Active'
DCC_STATUS_WAITACK = 'Waiting for ACK'
DCC_STATUS_CLOSING = 'Closing'
DCC_STATUS_CLOSED = 'Closed'

# ---------------------------------------------------------------------------
# DCC error constants
# ---------------------------------------------------------------------------
DCC_ERROR_ADMIN_CLOSED = 'Admin requested close'
DCC_ERROR_BROKENPIPE = 'Broken pipe'
DCC_ERROR_CONNECTION_REFUSED = 'Connection refused'
DCC_ERROR_INVALIDACK = 'Your client sent an invalid ACK'
DCC_ERROR_INTERNAL_NOTOPEN = 'Internal error: listener socket or file not open'
DCC_ERROR_INTERRUPTED = 'Interrupted system call'
DCC_ERROR_IOERROR = 'There was an error opening the file, please notify my owner'
DCC_ERROR_MULTI_LEECH = 'Multi-client leeching detected. My owner has been notified.'
DCC_ERROR_REMOTECLOSE = 'Connection closed by remote'
DCC_ERROR_RESETBYPEER = 'Connection reset by peer'
DCC_ERROR_RESUMEINDEX = 'DO NOT RESUME THE INDEX!'
DCC_ERROR_RESUMEPASTEOF = 'You tried to resume past the end of the file'
DCC_ERROR_SENDINPROGRESS = 'Transfer has already started'
DCC_ERROR_SHUTDOWN = 'Shutting down'
DCC_ERROR_TIMEOUT = 'Transfer timed out'
DCC_ERROR_UNKNOWN = 'Unknown error'

# ---------------------------------------------------------------------------
# Random stuff
# ---------------------------------------------------------------------------
INDEX_PACK = -1
