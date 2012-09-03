import logging, os
import email
import email.mime.multipart
import email.mime.text
import smtplib, cStringIO
from email.header import Header

log = logging.getLogger( __name__ )

class HeaderDefinition:
    end_tag                 = '\r\n'
    format_str_tag          = '%s: %s\r\n'
    from_tag                = 'From'
    to_tag                  = 'To'
    subject_tag             = 'Subject'
    reply_to_tag            = 'Reply-To'
    cc_tag                  = 'Cc'
    bcc_tag                 = 'Bcc'

class EmailSender:

    def __init__(self, 
                 from_addr, 
                 to_addr_list, 
                 subject, 
                 message, 
                 reply_to = None, 
                 sender = None):
        self.from_addr     = from_addr
        self.to_addr_list  = to_addr_list
        self.subject       = subject
        self.message       = message
        self.reply_to      = reply_to
        self.sender        = sender

    def send(self, smtp_host):
        try:
            fullMessage = cStringIO.StringIO()

            # Add headers to the message
            fullMessage.write(HeaderDefinition.format_str_tag % ( HeaderDefinition.from_tag, self.from_addr))
            if self.sender:
                fullMessage.write(HeaderDefinition.format_str_tag % ("Sender", self.sender))
            fullMessage.write(HeaderDefinition.format_str_tag % ( HeaderDefinition.to_tag, ', '.join( self.to_addr_list)))
            fullMessage.write(HeaderDefinition.format_str_tag % (HeaderDefinition.subject_tag, self.subject))

            if self.reply_to:
                fullMessage.write(HeaderDefinition.format_str_tag%(HeaderDefinition.reply_to_tag, self.reply_to))

            fullMessage.write(HeaderDefinition.end_tag)

            # Add the message body to the contents of the message
            fullMessage.write(self.message)

            mailServer = smtplib.SMTP(smtp_host)
            mailServer.sendmail(self.from_addr, self.to_addr_list, fullMessage.getvalue())
            mailServer.close()

        except Exception, ex:
            log.error("Error sending email - %s"%ex)

    def gmail_send(self):
        try:
            fullMessage = cStringIO.StringIO()

            # Add headers to the message
            fullMessage.write(HeaderDefinition.format_str_tag % ( HeaderDefinition.from_tag, self.from_addr))
            if self.sender:
                fullMessage.write(HeaderDefinition.format_str_tag % ("Sender", self.sender))
            fullMessage.write(HeaderDefinition.format_str_tag % ( HeaderDefinition.to_tag, ', '.join( self.to_addr_list)))
            fullMessage.write(HeaderDefinition.format_str_tag % (HeaderDefinition.subject_tag, self.subject))

            if self.reply_to:
                fullMessage.write(HeaderDefinition.format_str_tag%(HeaderDefinition.reply_to_tag, self.reply_to))

            fullMessage.write(HeaderDefinition.end_tag)

            # Add the message body to the contents of the message
            fullMessage.write(self.message)

            # Senf via gmail
            gmail_user = 'graphtool@gmail.com'
            gmail_pwd  = 'showmethegraph'
            smtpserver = smtplib.SMTP("smtp.gmail.com",587)
            smtpserver.ehlo()
            smtpserver.starttls()
            smtpserver.ehlo
            smtpserver.login(gmail_user, gmail_pwd)
            smtpserver.sendmail(gmail_user, self.to_addr_list, fullMessage.getvalue())
            smtpserver.close()

        except Exception, ex:
            log.error("Error sending email - %s"%ex)

