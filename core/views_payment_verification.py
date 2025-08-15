from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import FeePayment, Student
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


@login_required
@require_POST
def verify_payment_by_reference(request):
    """Approve a pending FeePayment when the provided reference matches.

    Scope rules:
    - Students can only verify their own pending payments by reference.
    - Admins can verify any student's pending payment by reference.
    """
    reference = (request.POST.get('reference') or '').strip()
    if not reference:
        return JsonResponse({'success': False, 'error': 'Reference code is required.'}, status=400)

    # Resolve student if requester is a student
    student = None
    if getattr(request.user, 'role', None) == 'student':
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student profile not found.'}, status=400)

    qs = FeePayment.objects.filter(status='pending', reference__iexact=reference)
    if student is not None:
        qs = qs.filter(student=student)

    payment = qs.first()
    if not payment:
        return JsonResponse({'success': False, 'error': 'No pending payment found with that reference.'}, status=404)

    payment.status = 'approved'
    payment.save(update_fields=['status'])

    return JsonResponse({
        'success': True,
        'payment_id': payment.id,
        'status': payment.status,
        'amount': str(payment.amount_paid),
        'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
    })
