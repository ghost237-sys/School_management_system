import email
import imaplib
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from core.models import User, Message

class Command(BaseCommand):
    help = 'Fetches all emails sent to users and saves them as messages.'

    def handle(self, *args, **options):
        EMAIL_HOST_USER = getattr(settings, 'EMAIL_HOST_USER', None)
        EMAIL_HOST_PASSWORD = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        IMAP_HOST = getattr(settings, 'IMAP_HOST', 'imap.gmail.com')
        IMAP_PORT = getattr(settings, 'IMAP_PORT', 993)

        if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            self.stderr.write('Email credentials not set in settings.py')
            return

        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        # Use the correct Gmail sent folder
        status, _ = mail.select('"[Gmail]/Sent Mail"')
        if status != 'OK':
            status, _ = mail.select('Sent')  # fallback
            if status != 'OK':
                self.stderr.write('Could not select Sent folder. Checked both Gmail and generic names.')
                return

        # Search for all sent emails
        status, data = mail.search(None, 'ALL')
        if status != 'OK':
            self.stderr.write('Failed to fetch sent emails. IMAP status: ' + status)
            return

        email_ids = data[0].split()
        if not email_ids:
            self.stdout.write('No sent emails found.')
            mail.logout()
            return

        for eid in email_ids:
            status, msg_data = mail.fetch(eid, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            to_emails = email.utils.getaddresses(msg.get_all('To', []))
            cc_emails = email.utils.getaddresses(msg.get_all('Cc', []))
            bcc_emails = email.utils.getaddresses(msg.get_all('Bcc', []))
            all_recipients = set([addr[1].lower() for addr in (to_emails + cc_emails + bcc_emails)])

            subject = msg['Subject'] or ''
            date = msg['Date']
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain' and not part.get('Content-Disposition'):
                        body = part.get_payload(decode=True).decode(errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')

            # For each recipient, if they are a user in User model, save as a sent message
            for email_addr in all_recipients:
                try:
                    user = User.objects.get(email__iexact=email_addr)
                except User.DoesNotExist:
                    continue
                # Find admin user (sender)
                try:
                    admin_user = User.objects.filter(role='admin').first()
                except User.DoesNotExist:
                    continue
                # Avoid duplicate messages (optional: check by content+date)
                message_content = f"[EMAIL SUBJECT: {subject}]\n{body.strip()}"
                if Message.objects.filter(sender=admin_user, recipient=user, content=message_content).exists():
                    continue
                Message.objects.create(
                    sender=admin_user,
                    recipient=user,
                    content=message_content,
                    timestamp=timezone.now(),
                    is_read=False
                )
                self.stdout.write(f'Saved sent email to {email_addr} as message.')

        mail.logout()
        self.stdout.write('Done fetching sent emails to users.')
