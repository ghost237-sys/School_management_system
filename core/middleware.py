from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

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
        return response

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
