from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.core.mail import send_mail
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.core import signing
from django.core.cache import cache
from django.utils import timezone
import random
from datetime import timedelta

# Wrapper login view: if prior idle logout detected, send a one-time login link to admin's email
# Then delegate to existing login view for normal processing

def login_with_idle_link(request):
    try:
        if request.method == 'GET' and request.session.pop('idle_logout', False):
            email = request.session.pop('idle_logout_email', '')
            if email:
                _send_idle_login_link(request, email)
                messages.info(request, f"A login link has been sent to {email}. Check your email to continue.")
    except Exception:
        # Non-fatal; continue to login flow
        pass

    # Delegate to the existing login view
    from .views import custom_login_view  # import here to avoid circulars on module import
    return custom_login_view(request)


def _send_idle_login_link(request, email: str) -> None:
    User = get_user_model()
    try:
        user = User.objects.get(email__iexact=email)
        if getattr(user, 'role', None) != 'admin':
            return
    except User.DoesNotExist:
        return

    payload = {
        'uid': user.pk,
        'ts': int(timezone.now().timestamp()),
        'purpose': 'idle_login',
    }
    token = signing.dumps(payload, salt='idle-login')
    url = request.build_absolute_uri(
        reverse('idle_login', kwargs={'token': token})
    )

    subject = f"{getattr(settings, 'SCHOOL_NAME', 'School')} Admin Login Link"
    message = (
        "You were logged out due to inactivity.\n\n"
        f"Click this one-time link to log back in: {url}\n\n"
        "This link expires in 15 minutes. If you did not request this, you can ignore this email."
    )
    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [email],
            fail_silently=False,
        )
        # Helpful for testing: also show link when DEBUG is on
        if getattr(settings, 'DEBUG', False):
            messages.info(request, f"Debug login link: {url}")
    except Exception as e:
        # Surface failure and provide the link inline so user can continue even if SMTP is blocked
        messages.error(request, f"Failed to send login link email: {e}")
        messages.info(request, f"Use this one-time link to continue: {url}")
        return


def idle_login(request, token: str):
    """
    Consume the one-time signed token and log in the admin if valid and not expired.
    Links expire after 15 minutes.
    """
    try:
        data = signing.loads(token, salt='idle-login', max_age=15 * 60)
        uid = data.get('uid')
        if data.get('purpose') != 'idle_login':
            return HttpResponseBadRequest('Invalid token purpose')
    except signing.BadSignature:
        messages.error(request, 'Invalid or expired login link.')
        return redirect(reverse('login'))
    except signing.SignatureExpired:
        messages.error(request, 'This login link has expired. Please log in again.')
        return redirect(reverse('login'))

    User = get_user_model()
    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect(reverse('login'))

    if getattr(user, 'role', None) != 'admin':
        return HttpResponseForbidden('Not allowed')

    # Log the user in without password (trusted link)
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    # Store simple device metadata on the session for display
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR') or ''
    request.session['device_user_agent'] = ua
    request.session['device_ip'] = ip
    request.session['device_login_time'] = timezone.now().isoformat()
    messages.success(request, 'Logged in via email link.')
    return redirect('admin_overview')


# --- Email confirmation login for Admin and Clerk (Finance) ---
def send_email_login_link(request, user, request_id: str | None = None):
    """
    Generate and email a one-time login confirmation link for the given user.
    Applies to roles: 'admin' and 'clerk'.
    Link expires in 15 minutes.
    """
    role = getattr(user, 'role', None)
    if role not in ('admin', 'clerk'):
        return

    payload = {
        'uid': user.pk,
        'role': role,
        'ts': int(timezone.now().timestamp()),
        'purpose': 'email_confirm_login',
    }
    if request_id:
        payload['rid'] = request_id
    token = signing.dumps(payload, salt='email-confirm-login')
    url = request.build_absolute_uri(
        reverse('email_login_confirm', kwargs={'token': token})
    )

    subject = f"{getattr(settings, 'SCHOOL_NAME', 'School')} {role.title()} Login Confirmation"
    message = (
        f"A login attempt was made for your {role} account.\n\n"
        f"Click this one-time link to confirm and complete login: {url}\n\n"
        "This link expires in 15 minutes. If this wasn't you, please ignore this email."
    )
    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [user.email],
            fail_silently=False,
        )
        # Helpful for testing: also show link when DEBUG is on
        if getattr(settings, 'DEBUG', False):
            messages.info(request, f"Debug login link: {url}")
    except Exception as e:
        # Surface failure and provide the link inline so user can continue even if SMTP is blocked
        messages.error(request, f"Failed to send login link email: {e}")
        messages.info(request, f"Use this one-time link to continue: {url}")
        return


def email_login_confirm(request, token: str):
    """
    Show a confirmation page first (GET). Only log the user in after explicit acceptance (POST).
    Supports roles 'admin' and 'clerk'.
    """
    try:
        data = signing.loads(token, salt='email-confirm-login', max_age=15 * 60)
        if data.get('purpose') != 'email_confirm_login':
            return HttpResponseBadRequest('Invalid token purpose')
        uid = data.get('uid')
        role = data.get('role')
        rid = data.get('rid')
    except signing.BadSignature:
        messages.error(request, 'Invalid or expired login link.')
        return redirect(reverse('login'))
    except signing.SignatureExpired:
        messages.error(request, 'This login link has expired. Please try logging in again.')
        return redirect(reverse('login'))

    User = get_user_model()
    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect(reverse('login'))

    if getattr(user, 'role', None) not in ('admin', 'clerk') or getattr(user, 'role') != role:
        return HttpResponseForbidden('Not allowed')

    if request.method == 'GET':
        # Show confirmation page
        return render(request, 'auth/email_login_confirm.html', {
            'token': token,
            'role': role,
            'email': user.email,
        })

    # POST: check acceptance
    action = request.POST.get('action')
    if action != 'accept':
        messages.info(request, 'Login request declined.')
        return redirect('login')

    # Mark this login request as accepted for device continuation
    if rid:
        cache.set(f"email_login:{rid}", {'status': 'accepted', 'uid': user.pk, 'role': role}, timeout=15 * 60)
    messages.success(request, 'Login confirmed. Return to your device to continue.')
    return render(request, 'auth/email_login_confirm.html', {
        'token': token,
        'role': role,
        'email': user.email,
        'accepted': True,
    })


from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required
def login_status(request, request_id: str):
    """Polled by the original device. If accepted, log in this session and return redirect URL."""
    data = cache.get(f"email_login:{request_id}")
    if not data or data.get('status') != 'accepted':
        return JsonResponse({'ok': False})

    # Perform login for this session
    User = get_user_model()
    try:
        user = User.objects.get(pk=data.get('uid'))
    except User.DoesNotExist:
        return JsonResponse({'ok': False})
    role = data.get('role')
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    # Invalidate the token so it can't be reused
    cache.delete(f"email_login:{request_id}")

    redirect_url = 'admin_overview' if role == 'admin' else ('clerk_overview' if role == 'clerk' else 'dashboard')
    return JsonResponse({'ok': True, 'redirect': reverse(redirect_url)})


@login_required(login_url='login')
def session_devices(request):
    """List active sessions for the current user across devices."""
    user = request.user
    sessions = []
    for s in Session.objects.all():
        try:
            data = s.get_decoded()
        except Exception:
            continue
        if str(data.get('_auth_user_id')) != str(user.id):
            continue
        sessions.append({
            'session_key': s.session_key,
            'expire_date': s.expire_date,
            'ua': data.get('device_user_agent', ''),
            'ip': data.get('device_ip', ''),
            'login_time': data.get('device_login_time', ''),
            'current': (s.session_key == request.session.session_key),
        })
    # Sort: current first, then newest by expire_date
    sessions.sort(key=lambda x: (not x['current'], x['expire_date'] or 0))
    return render(request, 'auth/sessions.html', {'sessions': sessions})


@login_required(login_url='login')
def revoke_session(request, key: str):
    """Allow a user to revoke a specific session (log out that device)."""
    if request.method != 'POST':
        return redirect('session_devices')
    try:
        # Prevent removing current session via this endpoint for safety
        if key == request.session.session_key:
            messages.info(request, 'You are currently using this session.')
            return redirect('session_devices')
        Session.objects.get(session_key=key).delete()
        messages.success(request, 'Device session revoked.')
    except Session.DoesNotExist:
        messages.error(request, 'Session not found or already expired.')
    return redirect('session_devices')


# --- OTP for sensitive actions ---
@login_required(login_url='login')
def send_action_otp(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        payload = json_from_body(request)
    except Exception:
        payload = {}
    context = str(payload.get('context') or '')[:50]

    # Throttle: allow one code every 30 seconds
    now = timezone.now()
    last_ts = request.session.get('otp_last_sent_at')
    if last_ts:
        try:
            last_dt = timezone.datetime.fromisoformat(last_ts)
            if (now - last_dt).total_seconds() < 30:
                return JsonResponse({'ok': True})
        except Exception:
            pass

    code = f"{random.randint(0, 999999):06d}"
    request.session['otp_code'] = code
    request.session['otp_expires_at'] = (now + timedelta(minutes=10)).isoformat()
    request.session['otp_context'] = context
    request.session['otp_last_sent_at'] = now.isoformat()
    try:
        email = getattr(request.user, 'email', None)
        if email:
            subject = f"{getattr(settings, 'SCHOOL_NAME', 'School')} Verification Code"
            msg = f"Your verification code is {code}. It expires in 10 minutes."
            send_mail(
                subject,
                msg,
                getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                [email],
                fail_silently=False,
            )
            # Helpful for testing: also show link when DEBUG is on
            if getattr(settings, 'DEBUG', False):
                messages.info(request, f"Debug verification code: {code}")
    except Exception as e:
        # Surface failure and provide the code inline so user can continue even if SMTP is blocked
        messages.error(request, f"Failed to send verification code email: {e}")
        messages.info(request, f"Use this one-time code to continue: {code}")
        return
    return JsonResponse({'ok': True})


@login_required(login_url='login')
def verify_action_otp(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        payload = json_from_body(request)
    except Exception:
        payload = {}
    code = str(payload.get('code') or '').strip()
    context = str(payload.get('context') or '')[:50]

    sess_code = request.session.get('otp_code')
    expires_at = request.session.get('otp_expires_at')
    sess_ctx = request.session.get('otp_context') or ''
    if not sess_code or not expires_at:
        return JsonResponse({'ok': False, 'error': 'No code issued'})
    try:
        exp_dt = timezone.datetime.fromisoformat(expires_at)
    except Exception:
        exp_dt = None
    if not exp_dt or timezone.now() > exp_dt:
        # Clear stale
        for k in ['otp_code','otp_expires_at','otp_context']:
            request.session.pop(k, None)
        return JsonResponse({'ok': False, 'error': 'Code expired'})
    if code != sess_code:
        return JsonResponse({'ok': False, 'error': 'Invalid code'})
    # Optional: ensure same context (if provided)
    if context and sess_ctx and context != sess_ctx:
        return JsonResponse({'ok': False, 'error': 'Context mismatch'})
    # Success: one-time use
    for k in ['otp_code','otp_expires_at','otp_context']:
        request.session.pop(k, None)
    return JsonResponse({'ok': True})


# Helper to parse JSON body safely
def json_from_body(request):
    import json as _json
    try:
        return _json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}
