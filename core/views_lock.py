from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# We will rely on the CSRF cookie/header for AJAX; do not exempt globally.
@require_POST
@login_required(login_url='login')
def verify_password(request):
    """
    AJAX endpoint to verify the current user's password while the UI is locked.
    Expects JSON or form-encoded with 'password'.
    Returns {ok: true} on success, 400 with {ok:false, error:"..."} on failure.
    """
    try:
        # Support both JSON and form-encoded
        password = request.POST.get('password')
        if password is None:
            import json
            try:
                data = json.loads(request.body.decode('utf-8')) if request.body else {}
            except Exception:
                data = {}
            password = data.get('password')

        if not password:
            return JsonResponse({'ok': False, 'error': 'Password required'}, status=400)

        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Not authenticated'}, status=401)

        if user.check_password(password):
            return JsonResponse({'ok': True})
        return JsonResponse({'ok': False, 'error': 'Invalid password'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'Server error'}, status=500)
