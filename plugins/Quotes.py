# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# Send quotes to an e-mail address, for _really_ lazy people

import re
import smtplib

from classes.Constants import *
from classes.Plugin import Plugin

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
		self.addTextEvent(
			method = self.__AddQuote,
			regexp = re.compile('^addquote (?P<quote>.+)$'),
			help = ('quotes', 'addquote', '\02addquote\02 <quote> : sends a quote to the configured e-mail address. Use || to seperate lines.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants to add a quote
	def __AddQuote(self, trigger):
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
			
			lines.append('\r\n')
			
			# Split the quote into lines
			qlines = [l.strip() for l in trigger.match.group('quote').split('||')]
			if qlines == []:
				self.sendReply(trigger, 'No valid lines in this quote!')
				return
			
			for qline in qlines:
				if qline:
					lines.append(qline)
			
			# Send the message!
			message = '\r\n'.join(lines)
			
			try:
				server = smtplib.SMTP(self.__server)
				server.sendmail(self.__from, self.__to, message)
				server.quit()
			
			except Exception, msg:
				replytext = 'Error sending mail: %s' % msg
				tolog = 'Error sending quote mail: %s' % msg
				self.putlog(LOG_WARNING, tolog)
			
			else:
				replytext = 'Mail sent successfully'
				tolog = '%s (%s@%s) sent a quote mail' % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host)
				self.putlog(LOG_ALWAYS, tolog)
			
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
