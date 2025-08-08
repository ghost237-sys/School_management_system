import email
import imaplib
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from core.models import User, Message

class Command(BaseCommand):
    help = 'Fetches email replies from Gmail and saves them as messages.'

    def handle(self, *args, **options):
        EMAIL_HOST_USER = getattr(settings, 'EMAIL_HOST_USER', None)
        EMAIL_HOST_PASSWORD = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        IMAP_HOST = getattr(settings, 'IMAP_HOST', 'imap.gmail.com')
        IMAP_PORT = getattr(settings, 'IMAP_PORT', 993)

        if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            self.stderr.write('Email credentials not set in settings.py')
            return

        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        mail.select('inbox')

        # Search for unseen replies (customize as needed)
        status, data = mail.search(None, '(UNSEEN)')
        if status != 'OK':
            self.stderr.write('Failed to fetch emails.')
            return

        email_ids = data[0].split()
        if not email_ids:
            self.stdout.write('No new replies found.')
            return

        for eid in email_ids:
            status, msg_data = mail.fetch(eid, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            from_email = email.utils.parseaddr(msg['From'])[1]
            subject = msg['Subject']
            date = msg['Date']

            # Get plain text body
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain' and not part.get('Content-Disposition'):
                        body = part.get_payload(decode=True).decode(errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')

            # Try to find user by email
            try:
                sender_user = User.objects.get(email__iexact=from_email)
            except User.DoesNotExist:
                self.stderr.write(f'No user found for email {from_email}')
                continue

            # Find admin user (recipient)
            try:
                admin_user = User.objects.filter(role='admin').first()
            except User.DoesNotExist:
                self.stderr.write('No admin user found.')
                continue

            # Save as a received message
            Message.objects.create(
                sender=sender_user,
                recipient=admin_user,
                content=body.strip(),
                timestamp=timezone.now(),
                is_read=False
            )
            self.stdout.write(f'Saved reply from {from_email} as message.')

            # Mark as seen
            mail.store(eid, '+FLAGS', '\\Seen')

        mail.logout()
        self.stdout.write('Done fetching replies.')
