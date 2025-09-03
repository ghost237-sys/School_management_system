from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import logout
import time

class ForbiddenRedirectMiddleware:
    """
    Intercept plain 403 HttpResponse and redirect users back to a safe previous page.
    This covers views that return HttpResponseForbidden instead of raising PermissionDenied.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if getattr(response, 'status_code', None) == 403:
                # Avoid redirect loops by not re-redirecting already redirected responses
                referer = request.META.get('HTTP_REFERER', '')
                from django.conf import settings as _settings
                if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts=set(_settings.ALLOWED_HOSTS)):
                    messages.error(request, 'You do not have permission to access that page.')
                    return redirect(referer)
                # Fallbacks
                if request.user.is_authenticated:
                    messages.error(request, 'You do not have permission to access that page.')
                    return redirect('/')
                else:
                    from django.urls import reverse
                    messages.error(request, 'Please login to continue.')
                    return redirect(reverse('login'))
        except Exception:
            # In any unexpected error, fall back to original response
            return response
        # For non-403 responses, pass the original response through
        return response

class IdleSessionTimeoutMiddleware:
    """
    If an authenticated admin user is inactive for settings.SESSION_IDLE_TIMEOUT seconds
    (default 1800 = 30min), automatically log them out and mark the session so that
    upon visiting the login page, a magic login link is emailed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, 'user', None)
            # Only enforce for logged-in admins
            if user and getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'admin':
                from django.conf import settings as _settings
                idle_timeout = int(getattr(_settings, 'SESSION_IDLE_TIMEOUT', 1800))
                now = int(time.time())
                last = request.session.get('last_activity_ts')
                # Update last activity for safe methods too; adjust if you want POST-only
                if last is None:
                    request.session['last_activity_ts'] = now
                else:
                    if now - int(last) > idle_timeout:
                        # Logout and mark idle flag; store email for magic link
                        email = getattr(user, 'email', '') or ''
                        logout(request)
                        request.session['idle_logout'] = True
                        if email:
                            request.session['idle_logout_email'] = email
                        # Inform user and redirect to login
                        messages.info(request, 'You were logged out due to inactivity.')
                        from django.urls import reverse
                        return redirect(reverse('login'))
                    else:
                        request.session['last_activity_ts'] = now
        except Exception:
            # Never block the request on middleware errors
            pass

        return self.get_response(request)

class NotFoundTemplateMiddleware:
    """
    Ensure 404 responses render our custom template (core/templates/404.html)
    even when DEBUG=True (which would otherwise show Django's technical 404).
    Must come AFTER CommonMiddleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if getattr(response, 'status_code', None) == 404 and not getattr(response, 'streaming', False):
                # Render our 404 template
                return render(request, '404.html', {'request_path': request.path}, status=404)
        except Exception:
            return response
        return response
