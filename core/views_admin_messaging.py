def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'admin'

def is_admin_or_clerk(user):
    return user.is_authenticated and getattr(user, 'role', None) in ('admin', 'clerk')

from django import forms
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .messaging_utils import send_sms_to_users

from django import forms
from django.http import JsonResponse

@login_required
@user_passes_test(is_admin)
def send_bulk_fee_arrears_notice(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    # Fast path: create a job and enqueue background task
    from .models import NotificationJob, Term
    from .tasks import send_fee_arrears_notifications
    from django.utils import timezone
    today = timezone.now().date()
    current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.filter(start_date__lte=today, end_date__isnull=True).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.order_by('-start_date').first()
    class_group_id = request.POST.get('class_group_id')
    job = NotificationJob.objects.create(job_type='fee_arrears', status='queued', meta={'term_id': getattr(current_term, 'id', None), 'class_group_id': class_group_id})
    send_fee_arrears_notifications.delay(job.id, getattr(current_term, 'id', None), int(class_group_id) if class_group_id else None)
    return JsonResponse({'success': True, 'job_id': job.id, 'message': 'Arrears notices are sending in the background.'})

from .models import User

class AdminMessageForm(forms.Form):
    recipients = forms.ModelMultipleChoiceField(queryset=User.objects.all().order_by('username'), required=True, label='Recipients', widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': '10'}))
    subject = forms.CharField(max_length=150, required=False)
    message = forms.CharField(widget=forms.Textarea, required=True)
    send_email = forms.BooleanField(required=False, initial=True)
    send_sms = forms.BooleanField(required=False, initial=False)


def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_send_message(request):
    form = AdminMessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        recipients = form.cleaned_data['recipients']
        subject = form.cleaned_data['subject'] or 'School Message'
        message_text = form.cleaned_data['message']
        send_email_opt = form.cleaned_data['send_email']
        send_sms_opt = form.cleaned_data['send_sms']
        email_failures = []
        sms_failures = []
        for recipient in recipients:
            # Email
            if send_email_opt and recipient.email:
                from django.core.mail import send_mail
                from django.conf import settings
                try:
                    send_mail(subject, message_text, settings.DEFAULT_FROM_EMAIL, [recipient.email])
                except Exception as e:
                    email_failures.append(f"{recipient}: {e}")
            # SMS
            if send_sms_opt:
                phone = None
                if hasattr(recipient, 'teacher') and recipient.teacher.phone:
                    phone = recipient.teacher.phone
                elif hasattr(recipient, 'student') and recipient.student.phone:
                    phone = recipient.student.phone
                elif hasattr(recipient, 'phone') and recipient.phone:
                    phone = recipient.phone
                if phone:
                    from .messaging_utils import send_sms
                    try:
                        sms_success, sms_response = send_sms(phone, message_text)
                        if not sms_success:
                            sms_failures.append(f"{recipient}: {sms_response}")
                    except Exception as e:
                        sms_failures.append(f"{recipient}: {e}")
                else:
                    sms_failures.append(f"{recipient}: No phone number assigned.")
        if email_failures or sms_failures:
            if email_failures:
                messages.error(request, f"Some emails failed: {'; '.join(email_failures)}")
            if sms_failures:
                messages.error(request, f"Some SMS failed: {'; '.join(sms_failures)}")
        else:
            messages.success(request, 'Messages sent successfully!')
        return redirect('admin_send_message')
    return render(request, 'dashboards/admin_send_message.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def admin_send_arrears_message(request):
    today = timezone.now().date()
    current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.filter(start_date__lte=today, end_date__isnull=True).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.order_by('-start_date').first()
    all_students = Student.objects.select_related('user', 'class_group').all()
    # Calculate total assigned and paid per student
    terms_up_to_current = Term.objects.filter(start_date__lte=current_term.start_date)
    arrears_students = []
    for student in all_students:
        assignments_for_student = FeeAssignment.objects.filter(class_group=student.class_group, term__in=terms_up_to_current)
        total_assigned = sum(a.amount for a in assignments_for_student)
        total_paid = FeePayment.objects.filter(student=student, fee_assignment__term__start_date__lte=current_term.start_date).aggregate(total=Sum('amount_paid'))['total'] or 0
        balance = total_assigned - total_paid
        if balance > 0.01:
            student.balance = balance
            arrears_students.append(student)
    import random
    def generate_formal_message(student):
        greetings = [
            f"Dear {student.user.get_full_name() or student.user.username},",
            "Dear Parent/Guardian,",
            f"Greetings {student.user.get_full_name() or student.user.username},",
            "Good day, Parent/Guardian,",
        ]
        name_block = f"Student Name: {student.user.get_full_name() or student.user.username}\nClass: {student.class_group.name}"
        bodies = [
            f"We wish to inform you that your child currently has an outstanding fee balance of Ksh. {student.balance:.2f}.",
            f"Our records indicate an outstanding balance of Ksh. {student.balance:.2f} for your child.",
            f"This is a polite reminder that there remains a fee balance of Ksh. {student.balance:.2f} for your child.",
            f"Kindly note that the fee arrears for your child amount to Ksh. {student.balance:.2f}.",
        ]
        closing = random.choice([
            "We kindly request that you clear this balance at your earliest convenience.",
            "Please make arrangements to settle the outstanding amount as soon as possible.",
            "Your prompt attention to this matter is appreciated.",
            "Thank you for your cooperation.",
        ])
        signature = random.choice([
            "\n\nBest regards,\nSchool Administration",
            "\n\nSincerely,\nSchool Accounts Office",
            "\n\nThank you,\nSchool Management",
            "\n\nSchool Administration",
        ])
        return f"{random.choice(greetings)}\n\n{name_block}\n\n{random.choice(bodies)}\n{closing}{signature}"

    if request.method == 'POST':
        recipient_ids = request.POST.getlist('recipients')
        subject = request.POST.get('subject') or 'Fee Payment Arrears Notification'
        message_template = request.POST.get('message')
        send_email = 'send_email' in request.POST
        send_sms = 'send_sms' in request.POST
        selected_students = [s for s in arrears_students if str(s.id) in recipient_ids]
        for student in selected_students:
            user = student.user
            context = {
                'student': student,
                'balance': student.balance,
                'class_group': student.class_group,
            }
            # If the admin hasn't customized the message, generate a formal, varied one
            if not message_template.strip() or message_template.strip() == "Dear Parent/Guardian,\n\nOur records indicate that there are outstanding fee balances for your child. Kindly clear the arrears of Ksh. {{ student.balance|floatformat:2 }} at your earliest convenience.\n\nThank you.\nSchool Administration":
                msg = generate_formal_message(student)
            else:
                # Render message with placeholders
                msg = message_template.replace('{{ student.user.get_full_name }}', user.get_full_name() or user.username)
                msg = msg.replace('{{ student.class_group.name }}', student.class_group.name)
                msg = msg.replace('{{ student.balance }}', f"{student.balance:.2f}")
                # If no balance placeholder, append the figure at the end
                if '{{ student.balance }}' not in message_template and f"{student.balance:.2f}" not in msg:
                    msg += f"\nOutstanding Balance: Ksh. {student.balance:.2f}"
            # Email
            if send_email and user.email:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(subject, msg, settings.DEFAULT_FROM_EMAIL, [user.email])
            # SMS
            if send_sms:
                phone = getattr(student, 'phone', None) or getattr(user, 'phone', None)
                if phone:
                    from .messaging_utils import send_sms
                    send_sms(phone, msg)
        messages.success(request, f'Arrears notice sent to {len(selected_students)} parent(s)/guardian(s).')
        return redirect('admin_send_arrears_message')
    return render(request, 'dashboards/admin_send_arrears_message.html', {'arrears_students': arrears_students})

from .models import FeePayment, Student, User
from django.db.models import Q

from django.views.decorators.http import require_GET

@login_required
@user_passes_test(is_admin)
@require_GET
def get_users_by_category(request):
    from .models import User, Student, Teacher, Class
    from django.db.models import Q, Sum
    category = request.GET.get('category')
    users = []
    # --- Category logic ---
    if category == 'all_students':
        users = User.objects.filter(role='student').order_by('username')
    elif category == 'students_with_balance':
        # Students with fee balance > 0
        students = Student.objects.select_related('user', 'class_group')
        user_ids = []
        for s in students:
            from .models import FeeAssignment, FeePayment, Term
            fee_assignments = FeeAssignment.objects.filter(class_group=s.class_group)
            total_billed = fee_assignments.aggregate(total=Sum('amount'))['total'] or 0
            total_paid = FeePayment.objects.filter(student=s).aggregate(total=Sum('amount_paid'))['total'] or 0
            if (total_billed - total_paid) > 0.01:
                user_ids.append(s.user.id)
        users = User.objects.filter(id__in=user_ids)
    elif category == 'students_without_balance':
        students = Student.objects.select_related('user', 'class_group')
        user_ids = []
        for s in students:
            from .models import FeeAssignment, FeePayment, Term
            fee_assignments = FeeAssignment.objects.filter(class_group=s.class_group)
            total_billed = fee_assignments.aggregate(total=Sum('amount'))['total'] or 0
            total_paid = FeePayment.objects.filter(student=s).aggregate(total=Sum('amount_paid'))['total'] or 0
            if (total_billed - total_paid) <= 0.01:
                user_ids.append(s.user.id)
        users = User.objects.filter(id__in=user_ids)
    elif category == 'all_teachers':
        users = User.objects.filter(role='teacher').order_by('username')
    elif category == 'class_teachers':
        teachers = Teacher.objects.exclude(class_teacher_for=None).select_related('user')
        users = [t.user for t in teachers]
    elif category == 'all_users':
        users = User.objects.all().order_by('username')
    elif category and category.startswith('level_'):
        try:
            level_num = int(category.split('_')[1])
            classes = Class.objects.filter(level=level_num)
            students = Student.objects.filter(class_group__in=classes).select_related('user')
            users = [s.user for s in students]
        except Exception:
            users = []
    else:
        users = []
    data = {
        'success': True,
        'users': [
            {'id': user.id, 'name': user.get_full_name() or user.username}
            for user in users
        ]
    }
    return JsonResponse(data)


@login_required
@user_passes_test(is_admin)
def admin_messaging(request):
    from core.models import User, Message
    category = request.GET.get('recipient_category', '')
    recipient_id = request.GET.get('recipient')
    recipients = []
    selected_user = None
    chat_history = []
    from core.models import Message
    if category == 'student':
        recipients = User.objects.filter(role='student')
    elif category == 'teacher':
        recipients = User.objects.filter(role='teacher')
    elif category == 'admin':
        recipients = User.objects.filter(role='admin')
    # Annotate each recipient with their latest message timestamp (sent or received)
    recipients = list(recipients)
    def latest_msg_time(user):
        msg = Message.objects.filter(
            (Q(sender=request.user, recipient=user) | Q(sender=user, recipient=request.user))
        ).order_by('-timestamp').first()
        return msg.timestamp if msg else None
    from datetime import datetime
    from django.utils import timezone
    recipients.sort(key=lambda u: latest_msg_time(u) or timezone.make_aware(datetime.min), reverse=True)
    # Per-user unread badge: store last opened timestamp for each user in session
    now = timezone.now().isoformat()
    last_opened_map = request.session.get('messaging_last_opened', {})
    # Compute unread message count since last opened for each user
    recipients_list = []
    for u in recipients:
        last_opened = last_opened_map.get(str(u.id))
        if last_opened:
            try:
                last_opened_dt = datetime.fromisoformat(last_opened)
                if timezone.is_naive(last_opened_dt):
                    last_opened_dt = timezone.make_aware(last_opened_dt)
            except Exception:
                last_opened_dt = timezone.make_aware(datetime.fromtimestamp(0))
        else:
            last_opened_dt = timezone.make_aware(datetime.fromtimestamp(0))
        # Find the latest admin reply to this user
        last_admin_reply = Message.objects.filter(sender=request.user, recipient=u).order_by('-timestamp').first()
        if last_admin_reply:
            last_admin_time = last_admin_reply.timestamp
        else:
            last_admin_time = timezone.make_aware(datetime.fromtimestamp(0))
        # Count all messages from user sent after admin's last message
        unread_count = Message.objects.filter(sender=u, recipient=request.user, timestamp__gt=last_admin_time).count()
        recipients_list.append({
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'role': u.role,
            'unread_count': unread_count,
        })
    # Resolve selected_user if provided
    if recipient_id:
        try:
            selected_user = next((u for u in recipients if str(u.id) == str(recipient_id)), None)
        except Exception:
            selected_user = None
    # If a chat is opened (selected_user), update last_opened and mark messages as read
    if selected_user:
        # Mark messages from selected_user to admin as read
        from core.models import Message
        Message.objects.filter(sender=selected_user, recipient=request.user, is_read=False).update(is_read=True)
        last_opened_map[str(selected_user.id)] = timezone.now().isoformat()
        request.session['messaging_last_opened'] = last_opened_map
    # Handle sending a message
    if request.method == 'POST' and selected_user:
        content = request.POST.get('message', '').strip()
        if content:
            Message.objects.create(sender=request.user, recipient=selected_user, content=content)
            # Send email
            email_sent = sms_sent = False
            email_error = sms_error = None
            if selected_user.email:
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    send_mail('New Message', content, settings.DEFAULT_FROM_EMAIL, [selected_user.email])
                    email_sent = True
                except Exception as e:
                    email_error = str(e)
            # Send SMS
            phone = getattr(selected_user, 'phone', None)
            if not phone and hasattr(selected_user, 'student') and hasattr(selected_user.student, 'phone'):
                phone = selected_user.student.phone
            if not phone and hasattr(selected_user, 'teacher') and hasattr(selected_user.teacher, 'phone'):
                phone = selected_user.teacher.phone
            if phone:
                try:
                    from .messaging_utils import send_sms
                    sms_success, sms_response = send_sms(phone, content)
                    sms_sent = sms_success
                    if not sms_success:
                        sms_error = sms_response
                except Exception as e:
                    sms_error = str(e)
            # Feedback messages
            from django.contrib import messages
            if email_sent and sms_sent:
                messages.success(request, 'Message sent, email and SMS delivered!')
            elif email_sent:
                messages.warning(request, 'Message sent and delivered via email, but SMS failed.')
            elif sms_sent:
                messages.warning(request, 'Message sent and delivered via SMS, but email failed.')
            else:
                messages.error(request, f'Message sent, but delivery failed. Email error: {email_error}, SMS error: {sms_error}')
        # After sending, redirect to GET to avoid resubmission
        return redirect(f"{request.path}?recipient_category={category}&recipient={recipient_id}")
    # Load chat history
    if selected_user:
        chat_history = Message.objects.filter(
            (Q(sender=request.user, recipient=selected_user) | Q(sender=selected_user, recipient=request.user))
        ).order_by('timestamp')
        chat_history = [
            {'id': m.id, 'sender_id': m.sender.id, 'content': m.content, 'timestamp': m.timestamp, 'is_read': m.is_read}
            for m in chat_history
        ]
    context = {
        'recipients': recipients_list,
        'selected_category': category,
        'selected_recipient_id': str(recipient_id) if recipient_id else '',
        'selected_user': {'id': selected_user.id, 'name': selected_user.get_full_name() or selected_user.username, 'role': selected_user.role} if selected_user else None,
        'chat_history': chat_history,
    }
    return render(request, 'dashboards/admin_messaging.html', context)

# --- AJAX/JSON Endpoints for enhanced messaging UX ---
from django.views.decorators.http import require_GET, require_POST
from django.utils.dateparse import parse_datetime
from django.utils import timezone

@login_required
@user_passes_test(is_admin)
@require_GET
def load_messages(request):
    """Return older messages before a given timestamp for pagination."""
    from core.models import Message, User
    recipient_id = request.GET.get('recipient')
    before = request.GET.get('before')
    page_size = int(request.GET.get('page_size', '20'))
    try:
        other = User.objects.get(id=int(recipient_id))
    except Exception:
        return JsonResponse({'messages': []})
    qs = Message.objects.filter(Q(sender=request.user, recipient=other) | Q(sender=other, recipient=request.user))
    if before:
        try:
            dt = parse_datetime(before)
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            if dt:
                qs = qs.filter(timestamp__lt=dt)
        except Exception:
            pass
    qs = qs.order_by('-timestamp')[:page_size]
    messages_list = []
    for m in reversed(list(qs)):
        messages_list.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'content': m.content,
            'timestamp_iso': m.timestamp.isoformat(),
            'time_hm': m.timestamp.strftime('%H:%M'),
        })
    data = {
        'current_user_id': request.user.id,
        'other_initial': (other.get_full_name() or other.username or '?')[:1].upper(),
        'messages': messages_list,
    }
    return JsonResponse(data)

@login_required
@user_passes_test(is_admin)
@require_POST
def mark_read(request):
    """Mark all messages from recipient to current user as read."""
    from core.models import Message, User
    rid = request.POST.get('recipient')
    try:
        other = User.objects.get(id=int(rid))
    except Exception:
        return JsonResponse({'success': False})
    updated = Message.objects.filter(sender=other, recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True, 'updated': updated})

@login_required
@user_passes_test(is_admin)
@require_POST
def conversation_action(request):
    """Pin/mute/archive conversation using session storage (no DB migration)."""
    rid = request.POST.get('recipient')
    action = request.POST.get('action')  # pin|unpin|mute|unmute|archive|unarchive
    store = request.session.get('messaging_flags', {'pinned': [], 'muted': [], 'archived': []})
    lists = {'pin': 'pinned', 'unpin': 'pinned', 'mute': 'muted', 'unmute': 'muted', 'archive': 'archived', 'unarchive': 'archived'}
    if action not in lists:
        return JsonResponse({'success': False, 'error': 'invalid action'}, status=400)
    key = lists[action]
    arr = set(map(str, store.get(key, [])))
    if action in ('pin', 'mute', 'archive'):
        arr.add(str(rid))
    else:
        arr.discard(str(rid))
    store[key] = list(arr)
    request.session['messaging_flags'] = store
    return JsonResponse({'success': True, 'flags': store})

@login_required
@user_passes_test(is_admin)
@require_POST
def upload_attachment(request):
    # Removed: attachment uploads are no longer supported.
    return JsonResponse({'success': False, 'error': 'Attachments disabled'}, status=410)

@login_required
@user_passes_test(is_admin_or_clerk)
def admin_payment_logs(request):
    import os, json, re
    from datetime import datetime
    logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'payment_callback_logs.txt')
    logs = ''
    entries = []
    if os.path.exists(logs_path):
        with open(logs_path, 'r', encoding='utf-8') as f:
            logs = f.read()
        # Try to parse as a JSON array first
        def try_parse_json_array(text):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    return data
            except Exception:
                return None
            return None
        parsed = try_parse_json_array(logs)
        # If not a valid array, attempt to extract JSON objects heuristically
        if parsed is None:
            chunks = []
            buf = []
            depth = 0
            for line in logs.splitlines():
                # Capture between balanced braces
                if '{' in line:
                    cnt = line.count('{')
                    depth += cnt
                if depth > 0:
                    buf.append(line)
                if '}' in line:
                    depth -= line.count('}')
                    if depth <= 0 and buf:
                        chunks.append('\n'.join(buf))
                        buf = []
                        depth = 0
            arr = []
            for ch in chunks:
                try:
                    arr.append(json.loads(ch))
                except Exception:
                    continue
            parsed = arr
        # Map parsed objects into friendly entries
        def get_item(items, name):
            try:
                for it in items or []:
                    if (it.get('Name') or '').lower() == name.lower():
                        return it.get('Value')
            except Exception:
                return None
            return None
        for obj in parsed or []:
            timestamp = obj.get('timestamp')
            status = obj.get('status') or 'success'
            details = obj.get('details') or obj
            body = ((details or {}).get('Body')) or details
            stk = ((body or {}).get('stkCallback')) or body
            meta = ((stk or {}).get('CallbackMetadata') or {}).get('Item')
            merchant_id = (stk or {}).get('MerchantRequestID') or (details or {}).get('MerchantRequestID')
            checkout_id = (stk or {}).get('CheckoutRequestID') or (details or {}).get('CheckoutRequestID')
            amount = get_item(meta, 'Amount')
            receipt = get_item(meta, 'MpesaReceiptNumber') or get_item(meta, 'M-PesaReceiptNumber')
            phone = get_item(meta, 'PhoneNumber')
            account_ref = get_item(meta, 'AccountReference') or get_item(meta, 'BillRefNumber')
            trans_date = get_item(meta, 'TransactionDate')
            balance = get_item(meta, 'Balance')
            entries.append({
                'timestamp': timestamp,
                'status': status,
                'amount': amount,
                'receipt': receipt,
                'phone': phone,
                'account_reference': account_ref,
                'transaction_date': trans_date,
                'balance': balance,
                'merchant_request_id': merchant_id,
                'checkout_request_id': checkout_id,
            })
        # Sort entries latest -> oldest
        def sort_key(e):
            dt = None
            # Try ISO-like timestamp first
            ts = e.get('timestamp')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace('Z','+00:00'))
                except Exception:
                    dt = None
            # Fallback to Mpesa TransactionDate format YYYYMMDDHHMMSS
            if dt is None:
                td = e.get('transaction_date')
                if td and isinstance(td, (str, int)):
                    s = str(td)
                    try:
                        dt = datetime.strptime(s, '%Y%m%d%H%M%S')
                    except Exception:
                        dt = None
            # Fallback to minimal value to push unknowns to the end
            return dt or datetime.min
        entries.sort(key=sort_key, reverse=True)
    context = {'logs': logs, 'entries': entries}
    return render(request, 'dashboards/admin_payment_logs.html', context)

@login_required
@user_passes_test(is_admin_or_clerk)
def admin_payment_messages(request):
    search = request.GET.get('search', '').strip()
    payments = FeePayment.objects.select_related('student__user', 'fee_assignment__class_group')
    if search:
        payments = payments.filter(
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(student__admission_no__icontains=search) |
            Q(fee_assignment__class_group__name__icontains=search) |
            Q(reference__icontains=search) |
            Q(phone_number__icontains=search)
        )
    payments = payments.order_by('-payment_date')
    return render(request, 'dashboards/admin_payment_messages.html', {'payments': payments})
