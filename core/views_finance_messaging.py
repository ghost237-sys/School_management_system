"""
views_finance_messaging.py
This module handles finance-related messaging for the School Management System.
You can add views here for sending finance notifications, receipts, reminders, etc.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages

# Import your models as needed
# from .models import User, Student, FeeAssignment, FeePayment, Term
def is_finance(user):
    return user.is_authenticated and getattr(user, 'role', None) in ['finance', 'admin']

from .forms import MessagingForm

@login_required
@user_passes_test(is_finance)
def finance_messaging_page(request):
    from .forms import MessagingForm
    from .models import Student, FeeAssignment, FeePayment, Term
    from django.core.mail import send_mail
    from django.utils import timezone
    from django.db.models import Sum
    show_full_form = True
    if request.method == 'POST':
        form = MessagingForm(request.POST)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        response_data = {}
        if form.data.getlist('recipient'):
            if form.is_valid() and (form.cleaned_data.get('send_email') or form.cleaned_data.get('send_sms')):
                today = timezone.now().date()
                current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
                recipient_users = form.cleaned_data['recipient']
                subject = form.cleaned_data['subject']
                message_template = form.cleaned_data['message']
                send_email = form.cleaned_data.get('send_email')
                send_sms = form.cleaned_data.get('send_sms')
                sent_count = 0
                sms_count = 0
                from .models import FinanceMessageHistory
                from django.conf import settings
                # Resolve school name
                school_name = getattr(settings, 'SCHOOL_NAME', 'Your School')
                try:
                    from landing.models import SiteSettings
                    s = SiteSettings.objects.first()
                    if s and s.school_name:
                        school_name = s.school_name
                except Exception:
                    pass
                subject_prefix = f"[{school_name}] " if school_name else ""
                for user in recipient_users:
                    student = Student.objects.filter(user=user).first()
                    if not student:
                        continue
                    fee_assignments = FeeAssignment.objects.filter(class_group=student.class_group)
                    total_billed = fee_assignments.aggregate(total=Sum('amount'))['total'] or 0
                    total_paid = FeePayment.objects.filter(student=student).aggregate(total=Sum('amount_paid'))['total'] or 0
                    balance = total_billed - total_paid
                    personalized_msg = message_template.replace('{fee_balance}', f'{balance:,.2f}')
                    if student and student.user:
                        personalized_msg = personalized_msg.replace('{student_name}', student.user.get_full_name() or student.user.username)
                        personalized_msg = personalized_msg.replace('{admission_no}', student.admission_no or '')
                    # Prefix school name to personalized message
                    personalized_msg = f"{school_name}: {personalized_msg}" if school_name else personalized_msg
                    # Email
                    email_status = None
                    if send_email and user.email:
                        email_status = 'sent'
                        try:
                            send_mail(subject_prefix + subject, personalized_msg, None, [user.email], fail_silently=False)
                            sent_count += 1
                        except Exception as e:
                            email_status = f'error: {str(e)}'
                            if is_ajax:
                                return JsonResponse({'success': False, 'error': f'Failed to send to {user.email}: {str(e)}'})
                            else:
                                from django.contrib import messages
                                messages.error(request, f'Failed to send to {user.email}: {str(e)}')
                        # Save email history
                        FinanceMessageHistory.objects.create(
                            recipient=user,
                            message_content=personalized_msg,
                            sent_by=request.user,
                            delivery_method='email',
                            status=email_status
                        )
                    # SMS
                    sms_status = None
                    if send_sms and student.phone:
                        try:
                            from .messaging_utils import send_sms as at_send_sms
                            ok, resp = at_send_sms(student.phone, personalized_msg)
                            if ok:
                                sms_status = 'sent'
                                sms_count += 1
                            else:
                                sms_status = f'error: {resp}'
                                if is_ajax:
                                    return JsonResponse({'success': False, 'error': f'Failed to send SMS to {student.phone}: {resp}'})
                                else:
                                    from django.contrib import messages
                                    messages.error(request, f'Failed to send SMS to {student.phone}: {resp}')
                        except Exception as e:
                            sms_status = f'error: {str(e)}'
                            if is_ajax:
                                return JsonResponse({'success': False, 'error': f'Failed to send SMS to {student.phone}: {str(e)}'})
                            else:
                                from django.contrib import messages
                                messages.error(request, f'Failed to send SMS to {student.phone}: {str(e)}')
                        # Save SMS history
                        FinanceMessageHistory.objects.create(
                            recipient=user,
                            message_content=personalized_msg,
                            sent_by=request.user,
                            delivery_method='sms',
                            status=sms_status
                        )
                success_msg = f"Email sent: {sent_count}. SMS sent: {sms_count}."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': success_msg, 'email_sent': sent_count, 'sms_sent': sms_count})
                else:
                    messages.success(request, success_msg)
            else:
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Form invalid or email not selected.'})
        else:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'No recipients selected.'})
    else:
        form = MessagingForm()
    # If this is an AJAX POST and we haven't returned yet, return a generic error
    if request.method == 'POST' and is_ajax:
        return JsonResponse({'success': False, 'error': 'Unknown error. Please check your input and try again.'})
    from .models import FinanceMessageHistory
    message_history = FinanceMessageHistory.objects.select_related('recipient', 'sent_by').order_by('-sent_at')[:50]
    context = {
        'form': form,
        'show_full_form': show_full_form,
        'message_history': message_history,
    }
    return render(request, 'dashboards/finance_messaging.html', context)

def is_finance(user):
    return user.is_authenticated and getattr(user, 'role', None) in ['finance', 'admin']

# Example placeholder view for sending a finance message
@login_required
@user_passes_test(is_finance)
def send_finance_notice(request):
    if request.method == 'POST':
        # Implement finance message sending logic here
        return JsonResponse({'success': True, 'message': 'Finance notice sent!'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
