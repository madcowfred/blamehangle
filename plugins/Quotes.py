# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------

"Sends quotes to an e-mail address, for _really_ lazy people."

import smtplib

from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

class Quotes(Plugin):
	_HelpSection = 'misc'
	
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('Quotes')
	
	# ---------------------------------------------------------------------------
	
	def register(self):
		self.addTextEvent(
			method = self.__AddQuote,
			regexp = r'^addquote (?P<quote>.+)$',
			help = ('addquote', '\02addquote\02 <quote> : sends a quote to the configured e-mail address. Use || to seperate lines.'),
		)
	
	# -----------------------------------------------------------------------
	# Someone wants to add a quote
	def __AddQuote(self, trigger):
			# Build the message
			lines = []
			
			line = 'From: %s' % self.Options['mail_from']
			lines.append(line)
			
			line = 'To: %s' % self.Options['mail_to']
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
				server = smtplib.SMTP(self.Options['mail_server'])
				server.sendmail(self.Options['mail_from'], self.Options['mail_to'], message)
				server.quit()
			
			except Exception, msg:
				replytext = 'Error sending mail: %s' % (msg)
				tolog = 'Error sending quote mail: %s' % (msg)
				self.putlog(LOG_WARNING, tolog)
			
			else:
				replytext = 'Mail sent successfully'
				tolog = '%s (%s@%s) sent a quote mail' % (trigger.userinfo.nick, trigger.userinfo.ident, trigger.userinfo.host)
				self.putlog(LOG_ALWAYS, tolog)
			
			self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
