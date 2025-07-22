from django.utils import timezone
from datetime import datetime, time
from .models import Event
from django.core.mail import send_mail
from django.conf import settings
import requests

def create_event(title, date, end_date=None, all_day=True):
    """
    Create and store an event in the database.
    - title: Event title
    - date: date or datetime (for start)
    - end_date: date or datetime (optional)
    - all_day: bool
    """
    # Ensure start is timezone-aware datetime
    if isinstance(date, datetime):
        start_dt = timezone.make_aware(date) if timezone.is_naive(date) else date
    else:
        # If a date, combine with midnight
        start_dt = timezone.make_aware(datetime.combine(date, time.min))
    end_dt = None
    if end_date:
        if isinstance(end_date, datetime):
            end_dt = timezone.make_aware(end_date) if timezone.is_naive(end_date) else end_date
        else:
            end_dt = timezone.make_aware(datetime.combine(end_date, time.max))
    return Event.objects.create(title=title, start=start_dt, end=end_dt, all_day=all_day)

def send_exam_notification_email(recipients, subject, message):
    """
    Send exam notification emails.
    recipients: list of email addresses
    subject: email subject
    message: email body
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=False,
    )

def send_exam_notification_sms(phone_numbers, message):
    """
    Send exam notification SMS using Africa's Talking API.
    phone_numbers: list of phone numbers as strings
    message: SMS body
    """
    api_key = "atsk_636b3fe5172580a0eb210b5d570c19ff14fd292bfc0bb3ff58ea91e2b7e3b81a1062bca2"
    username = "sandbox"  # Change to your Africa's Talking username if not sandbox
    url = "https://api.africastalking.com/version1/messaging"
    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    for number in phone_numbers:
        data = {
            "username": username,
            "to": number,
            "message": message,
        }
        # For local development, do not send real SMS
        print(f"[DEV] Would send SMS to {number}: {message}")
