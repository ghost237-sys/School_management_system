from django.core.mail import send_mail
from django.conf import settings
from .models import User

# Placeholder for SMS sending (to be replaced with actual provider integration)
import requests

def send_sms(phone_number, message):
    """
    Send SMS using Africa's Talking API.
    phone_number: str, recipient phone number in international format
    message: str, SMS body
    """
    api_key = "atsk_cfa2b3d6126b2d39600d4793001e45abd42d97fe8ce5f87d970276378c5b9f18dea9afc5"
    username = "Sevenforks"  # Live Africa's Talking username for production
    url = "https://api.africastalking.com/version1/messaging"
    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "username": username,
        "to": phone_number,
        "message": message,
    }
    try:
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        resp_json = response.json()
        # Africa's Talking returns 'SMSMessageData' with 'Recipients' list
        if resp_json.get('SMSMessageData', {}).get('Recipients'):
            return True, resp_json
        else:
            print(f"Failed to send SMS: {resp_json}")
            return False, resp_json
    except Exception as e:
        print(f"Error sending SMS to {phone_number}: {e}")
        return False, str(e)


def get_users_by_role(role=None):
    """
    Return queryset of users filtered by role. If role is None, return all users.
    """
    if role:
        return User.objects.filter(role=role)
    return User.objects.all()


def send_email_to_users(subject, message, role=None):
    users = get_users_by_role(role)
    recipient_list = [u.email for u in users if u.email]
    if recipient_list:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        return True
    return False


def send_sms_to_users(message, role=None):
    users = get_users_by_role(role)
    for user in users:
        # Try to get phone from related profile (Teacher/Student), fallback to user.profile/phone if exists
        phone = None
        if hasattr(user, 'teacher') and user.teacher.phone:
            phone = user.teacher.phone
        elif hasattr(user, 'student') and user.student.phone:
            phone = user.student.phone
        elif hasattr(user, 'phone'):
            phone = user.phone
        if phone:
            send_sms(phone, message)
    return True
