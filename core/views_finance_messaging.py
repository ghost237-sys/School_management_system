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
    return user.is_authenticated and getattr(user, 'role', None) in ['clerk', 'admin']

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
                sms_logs = []  # collect per-recipient SMS results for modal display
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
                        try:
                            from django.conf import settings
                            # Check if we're using console backend (development mode)
                            if 'console' in settings.EMAIL_BACKEND:
                                # In console mode, emails are printed to terminal
                                send_mail(subject_prefix + subject, personalized_msg, None, [user.email], fail_silently=False)
                                email_status = 'sent (console)'
                                sent_count += 1
                            else:
                                # SMTP mode - try to send actual email
                                send_mail(subject_prefix + subject, personalized_msg, None, [user.email], fail_silently=False)
                                email_status = 'sent'
                                sent_count += 1
                        except Exception as e:
                            email_status = f'error: {str(e)}'
                            # Log the error but don't stop processing other recipients
                            print(f"Email send error for {user.email}: {str(e)}")
                            if is_ajax:
                                # For AJAX, show error but continue processing
                                continue
                            else:
                                from django.contrib import messages
                                messages.warning(request, f'Email failed for {user.email}: {str(e)}')
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
                        # Append to logs for modal (AJAX only)
                        sms_logs.append({
                            'user_id': getattr(user, 'id', None),
                            'recipient': (student.user.get_full_name() or student.user.username) if (student and student.user) else str(user),
                            'phone': student.phone,
                            'status': sms_status,
                            'message_preview': (personalized_msg[:120] + ('…' if len(personalized_msg) > 120 else '')),
                        })
                success_msg = f"Email sent: {sent_count}. SMS sent: {sms_count}."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': success_msg, 'email_sent': sent_count, 'sms_sent': sms_count, 'sms_logs': sms_logs})
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
    return user.is_authenticated and getattr(user, 'role', None) in ['clerk', 'admin']

# Example placeholder view for sending a finance message
@login_required
@user_passes_test(is_finance)
def send_finance_notice(request):
    if request.method == 'POST':
        # Implement finance message sending logic here
        return JsonResponse({'success': True, 'message': 'Finance notice sent!'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

@login_required
@user_passes_test(is_finance)
def resend_failed_sms(request):
    """AJAX endpoint to resend failed SMS to a list of user IDs.
    Expected JSON body: {"user_ids": [..], "subject": "...", "message": "..."}
    """
    if request.method != 'POST' or request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    import json
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    user_ids = payload.get('user_ids') or []
    subject = payload.get('subject') or ''
    message_template = payload.get('message') or ''
    if not user_ids:
        return JsonResponse({'success': False, 'error': 'No recipients provided.'}, status=400)

    from .models import User, Student, FeeAssignment, FeePayment, FinanceMessageHistory
    from django.utils import timezone
    from django.db.models import Sum
    from django.conf import settings as dj_settings

    # Resolve school name
    school_name = getattr(dj_settings, 'SCHOOL_NAME', 'Your School')
    try:
        from landing.models import SiteSettings
        s = SiteSettings.objects.first()
        if s and s.school_name:
            school_name = s.school_name
    except Exception:
        pass

    sms_count = 0
    logs = []
    for user in User.objects.filter(id__in=user_ids):
        student = Student.objects.filter(user=user).first()
        if not student or not student.phone:
            logs.append({
                'user_id': getattr(user, 'id', None),
                'recipient': user.get_full_name() or user.username,
                'phone': getattr(student, 'phone', ''),
                'status': 'error: missing phone/student',
                'message_preview': ''
            })
            continue
        fee_assignments = FeeAssignment.objects.filter(class_group=student.class_group)
        total_billed = fee_assignments.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = FeePayment.objects.filter(student=student).aggregate(total=Sum('amount_paid'))['total'] or 0
        balance = total_billed - total_paid
        personalized_msg = (message_template or '').replace('{fee_balance}', f'{balance:,.2f}')
        personalized_msg = personalized_msg.replace('{student_name}', student.user.get_full_name() or student.user.username)
        personalized_msg = personalized_msg.replace('{admission_no}', student.admission_no or '')
        personalized_msg = f"{school_name}: {personalized_msg}" if school_name else personalized_msg
        sms_status = None
        try:
            from .messaging_utils import send_sms as at_send_sms
            ok, resp = at_send_sms(student.phone, personalized_msg)
            if ok:
                sms_status = 'sent'
                sms_count += 1
            else:
                sms_status = f'error: {resp}'
        except Exception as e:
            sms_status = f'error: {str(e)}'
        FinanceMessageHistory.objects.create(
            recipient=user,
            message_content=personalized_msg,
            sent_by=request.user,
            delivery_method='sms',
            status=sms_status
        )
        logs.append({
            'user_id': getattr(user, 'id', None),
            'recipient': student.user.get_full_name() or student.user.username,
            'phone': student.phone,
            'status': sms_status,
            'message_preview': (personalized_msg[:120] + ('…' if len(personalized_msg) > 120 else '')),
        })
    return JsonResponse({'success': True, 'message': f'SMS resent: {sms_count}.', 'sms_sent': sms_count, 'sms_logs': logs})
