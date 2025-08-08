from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import FeePayment
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test

def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'admin'

@login_required
@user_passes_test(is_admin)
@require_POST
def verify_payment(request, payment_id):
    payment = get_object_or_404(FeePayment, id=payment_id)
    if payment.status != 'pending':
        return JsonResponse({'success': False, 'error': 'Payment already verified or rejected.'}, status=400)
    payment.status = 'approved'
    payment.save()
    return JsonResponse({'success': True, 'status': payment.get_status_display()})
