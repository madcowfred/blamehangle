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

"Sends quotes to an e-mail address, for _really_ lazy people."

import smtplib

from classes.Constants import *
from classes.Plugin import Plugin

# ---------------------------------------------------------------------------

SELECT_QUOTE = 'SELECT quote FROM quotes ORDER BY seen, RANDOM() LIMIT 1'
UPDATE_QUOTE = 'UPDATE quotes SET seen = seen + 1 WHERE quote = %s'

# ---------------------------------------------------------------------------

class Quotes(Plugin):
	_HelpSection = 'misc'
	_UsesDatabase = 'Quotes'
	
	def setup(self):
		self.rehash()
	
	def rehash(self):
		self.Options = self.OptionsDict('Quotes', autosplit=True)
	
	# ---------------------------------------------------------------------------
	
	def register(self):
		# Do we allow public addquote commands?
		if self.Options.get('allow_public_addquote', 1):
			self.addTextEvent(
				method = self.__AddQuote,
				regexp = r'^addquote (?P<quote>.+)$',
				help = ('addquote', '\02addquote\02 <quote> : sends a quote to the configured e-mail address. Use || to seperate lines.'),
			)
		else:
			self.addTextEvent(
				method = self.__AddQuote,
				regexp = r'^addquote (?P<quote>.+)$',
				help = ('addquote', '\02addquote\02 <quote> : sends a quote to the configured e-mail address. Use || to seperate lines.'),
				IRCTypes = (IRCT_MSG,),
			)
			self.addTextEvent(
				method = self.__AddQuoteNoPublic,
				regexp = r'^addquote (?P<quote>.+)$',
				IRCTypes = (IRCT_PUBLIC_D,),
			)
		
		# Do we want to spam quotes at an interval?
		if self.Options.get('spam_interval', 0) > 0:
			self.addTimedEvent(
				method = self.__Query_Spam,
				interval = self.Options['spam_interval'],
				targets = self.Options['spam_targets']
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
			
			line = 'Subject: Quote from %s' % (trigger.userinfo)
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
	
	# No public addquote!
	def __AddQuoteNoPublic(self, trigger):
		self.sendReply(trigger, "Don't use addquote in public!")
	
	# -----------------------------------------------------------------------
	# Time to get a new quote to spam
	def __Query_Spam(self, trigger):
		self.dbQuery(trigger, self.__Spam_Quote, SELECT_QUOTE)
	
	def __Spam_Quote(self, trigger, result):
		# Error!
		if result is None:
			replytext = 'An unknown database error occurred.'
		
		# No result!
		elif result == ():
			replytext = 'No quotes in database, someone sucks!'
		
		# Spam it!
		else:
			if self.Options['spam_prefix']:
				replytext = '%s %s' % (self.Options['spam_prefix'], result[0]['quote'])
			else:
				replytext = result[0]['quote']
			
			# And update the seen count
			self.dbQuery(trigger, None, UPDATE_QUOTE, result[0]['quote'])
		
		self.sendReply(trigger, replytext)

# ---------------------------------------------------------------------------
