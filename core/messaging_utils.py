from django.core.mail import send_mail, get_connection, EmailMessage
from django.conf import settings
from .models import User

# Placeholder for SMS sending (to be replaced with actual provider integration)
import requests
import time

def _normalize_msisdn(msisdn: str) -> str:
    """Normalize a phone number to E.164 using DEFAULT_SMS_COUNTRY_CODE.
    Rules:
    - Strip spaces, dashes, parentheses.
    - If starts with '+', return as-is.
    - If starts with the plain country code, prefix '+'.
    - If starts with '0', replace leading '0' with '+<CC>'.
    - If it's 9-10 digits and looks like a local mobile (leading 7/1 or 07/01 for KE), prefix '+<CC>'.
    """
    if not msisdn:
        return msisdn
    s = ''.join(ch for ch in str(msisdn) if ch.isdigit() or ch == '+')
    if s.startswith('+'):
        return s
    cc = getattr(settings, 'DEFAULT_SMS_COUNTRY_CODE', '254') or '254'
    cc = ''.join(ch for ch in str(cc) if ch.isdigit())
    if s.startswith(cc):
        return '+' + s
    if s.startswith('0'):
        return f'+{cc}' + s[1:]
    # Fallback heuristics for common local formats
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) == 9 and digits[0] in ('7', '1'):
        return f'+{cc}' + digits
    if len(digits) == 10 and digits[0] == '0':
        return f'+{cc}' + digits[1:]
    return s

def _is_valid_ke_msisdn(msisdn: str) -> bool:
    """Very small validator for Kenyan mobile numbers in E.164.
    Accepts +2547XXXXXXXX or +2541XXXXXXXX (Safaricom/Airtel/Telecom ranges).
    """
    if not msisdn:
        return False
    if not msisdn.startswith('+254'):
        return False
    digits = ''.join(ch for ch in msisdn if ch.isdigit())
    # +254 then 9 digits => total 13 chars including '+'
    if len(msisdn) != 13:
        return False
    # after country code should start with 7 or 1
    local_lead = digits[3]
    if local_lead not in ('7', '1'):
        return False
    return True

_requests_session = requests.Session()


def send_sms(phone_number, message):
    """
    Send SMS using Africa's Talking API.
    phone_number: str, recipient phone number in international format
    message: str, SMS body
    """
    # Respect global SMS toggle
    if not getattr(settings, 'SMS_ENABLED', True):
        return False, 'SMS disabled by configuration'

    api_key = getattr(settings, 'AFRICASTALKING_API_KEY', '')
    username = getattr(settings, 'AFRICASTALKING_USERNAME', '')
    if not api_key or not username:
        return False, 'Africa\'s Talking credentials not configured'

    # Normalize and validate
    normalized = _normalize_msisdn(phone_number)
    if not _is_valid_ke_msisdn(normalized):
        return False, 'InvalidPhoneNumber'

    # Use sandbox endpoint when username is 'sandbox'
    base_url = "https://api.sandbox.africastalking.com" if (username or '').lower() == 'sandbox' else "https://api.africastalking.com"
    url = f"{base_url}/version1/messaging"
    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "username": username,
        "to": normalized,
        "message": message,
    }
    # Optional: use configured sender ID when provided
    sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', '').strip()
    if sender_id:
        data["from"] = sender_id
    # Simple retry with exponential backoff to mitigate transient TLS/network glitches
    attempts = 3
    last_error = None
    for i in range(attempts):
        try:
            response = _requests_session.post(url, data=data, headers=headers, timeout=20)
            # Try to parse JSON regardless of status
            try:
                resp_json = response.json()
            except Exception:
                resp_json = None
            if response.status_code in (200, 201) and isinstance(resp_json, dict):
                recipients = (resp_json.get('SMSMessageData') or {}).get('Recipients') or []
                if recipients and all((r.get('status') or '').lower().startswith('success') for r in recipients):
                    return True, resp_json
                return False, resp_json
            # Non-200: return body for clarity
            if isinstance(resp_json, dict):
                err = resp_json.get('ErrorMessage') or resp_json.get('SMSMessageData') or resp_json
                return False, err
            return False, response.text
        except Exception as e:
            last_error = e
            # backoff: 0.5s, 1s
            if i < attempts - 1:
                time.sleep(0.5 * (2 ** i))
    return False, str(last_error) if last_error else 'Unknown error'


def _chunked(iterable, size):
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def send_sms_batch(phone_numbers, message):
    """Send one SMS to multiple recipients in a single Africa's Talking request.
    Returns: (success_count, errors: list[str]) with per-number statuses.
    """
    if not getattr(settings, 'SMS_ENABLED', True):
        return 0, ['SMS disabled by configuration']

    api_key = getattr(settings, 'AFRICASTALKING_API_KEY', '')
    username = getattr(settings, 'AFRICASTALKING_USERNAME', '')
    if not api_key or not username:
        return 0, ["Africa's Talking credentials not configured"]

    # Normalize and keep valid numbers only
    normalized = []
    invalid = []
    for n in phone_numbers:
        nn = _normalize_msisdn(n)
        if _is_valid_ke_msisdn(nn):
            normalized.append(nn)
        else:
            invalid.append(f"{n}: InvalidPhoneNumber")
    if not normalized:
        return 0, invalid if invalid else ['No valid recipients']

    base_url = "https://api.sandbox.africastalking.com" if (username or '').lower() == 'sandbox' else "https://api.africastalking.com"
    url = f"{base_url}/version1/messaging"
    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "username": username,
        "to": ",".join(normalized),
        "message": message,
    }
    sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', '').strip()
    if sender_id:
        data["from"] = sender_id

    attempts = 3
    last_error = None
    for i in range(attempts):
        try:
            response = _requests_session.post(url, data=data, headers=headers, timeout=30)
            try:
                resp_json = response.json()
            except Exception:
                resp_json = None
            success = 0
            errors = invalid.copy()
            if response.status_code in (200, 201) and isinstance(resp_json, dict):
                recips = (resp_json.get('SMSMessageData') or {}).get('Recipients') or []
                # Build a status map
                status_map = {}
                for r in recips:
                    status_map[str(r.get('number'))] = (r.get('status') or '').lower()
                for num in normalized:
                    st = status_map.get(num)
                    if st and st.startswith('success'):
                        success += 1
                    else:
                        errors.append(f"{num}: {st or 'Failed'}")
                return success, errors
            # Non-200
            if isinstance(resp_json, dict):
                errors.append(str(resp_json))
            else:
                errors.append(response.text)
            return 0, errors
        except Exception as e:
            last_error = e
            if i < attempts - 1:
                time.sleep(0.5 * (2 ** i))
    return 0, [str(last_error) if last_error else 'Unknown error']


def get_users_by_role(role=None):
    """
    Return queryset of users filtered by role. If role is None, return all users.
    """
    if role:
        return User.objects.filter(role=role)
    return User.objects.all()


def send_bulk_sms(phone_numbers, message, batch_size=100):
    """High-throughput SMS sending using Africa's Talking batch API.
    - Chunks recipients (default 100 per request) to respect provider limits.
    - Reuses HTTP session for performance.
    Returns: (success_count, errors: list[str])
    """
    success_total = 0
    errors_total = []
    for chunk in _chunked(phone_numbers, batch_size):
        s, e = send_sms_batch(chunk, message)
        success_total += s
        errors_total.extend(e)
    return success_total, errors_total


def send_email_to_users(subject, message, role=None, batch_size=100):
    """Send emails efficiently by reusing a single SMTP connection and batching BCC.
    Many providers limit visible recipients; we use BCC to protect privacy.
    Returns True if at least one message attempted.
    """
    users = get_users_by_role(role)
    recipient_list = [u.email for u in users if getattr(u, 'email', None)]
    if not recipient_list:
        return False
    attempted = False
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    # Reuse a single connection
    with get_connection() as connection:
        for chunk in _chunked(recipient_list, batch_size):
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[],  # keep To: empty to avoid exposing addresses
                bcc=chunk,
                connection=connection,
            )
            # Send immediately; connection persists across batches
            connection.send_messages([email])
            attempted = True
    return attempted


def send_sms_to_users(message, role=None, batch_size=100):
    users = get_users_by_role(role)
    phones = []
    for user in users:
        # Try to get phone from related profile (Teacher/Student), fallback to user.phone if exists
        phone = None
        if hasattr(user, 'teacher') and getattr(user.teacher, 'phone', None):
            phone = user.teacher.phone
        elif hasattr(user, 'student') and getattr(user.student, 'phone', None):
            phone = user.student.phone
        elif hasattr(user, 'phone') and getattr(user, 'phone', None):
            phone = user.phone
        if phone:
            phones.append(phone)
    if not phones:
        return True
    send_bulk_sms(phones, message, batch_size=batch_size)
    return True
