# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Send quotes to an e-mail address, for _really_ lazy people

import re
import smtplib

from classes.Constants import *
from classes.Plugin import *

# ---------------------------------------------------------------------------

QUOTES_ADDQUOTE = 'QUOTES_ADDQUOTE'
ADDQUOTE_HELP = '\02addquote\02 <quote> : sends a quote to the configured e-mail address'
ADDQUOTE_RE = re.compile('^addquote (?P<quote>.+)$')

# ---------------------------------------------------------------------------

class Quotes(Plugin):
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.__server = self.Config.get('Quotes', 'mail_server')
		self.__from = self.Config.get('Quotes', 'mail_from')
		self.__to = self.Config.get('Quotes', 'mail_to')
	
	# ---------------------------------------------------------------------------
	
	def register(self):
		self.setTextEvent(QUOTES_ADDQUOTE, ADDQUOTE_RE, IRCT_PUBLIC_D, IRCT_MSG)
		self.registerEvents()
		
		self.setHelp('quotes', 'addquote', ADDQUOTE_HELP)
		self.registerHelp()
	
	# -----------------------------------------------------------------------
	
	def _trigger_QUOTES_ADDQUOTE(self, trigger):
			# Build the message
			lines = []
			
			line = 'From: %s' % self.__from
			lines.append(line)
			
			line = 'To: %s' % self.__to
			lines.append(line)
			
			line = 'Subject: Quote from %s' % trigger.userinfo.hostmask
			lines.append(line)
			
			line = 'X-Mailer: blamehangle Quotes plugin'
			lines.append(line)
			
			lines.append(trigger.match.group('quote'))
			
			# Send it!
			message = '\r\n'.join(lines)
			
			# Send the message!
			try:
				server = smtplib.SMTP(self.__server)
				server.sendmail(self.__from, self.__to, message)
				server.quit()
			
			except:
				replytext = 'Error sending mail!'
			
			else:
				replytext = 'Mail sent successfully'
			
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
