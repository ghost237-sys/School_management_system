from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .messaging_utils import send_sms_to_users

# Simple form for messaging
from django import forms

from .models import User, Student, FeePayment, Term, FeeAssignment
from django.db.models import Sum
from django.utils import timezone

class AdminMessageForm(forms.Form):
    recipient = forms.ModelChoiceField(queryset=User.objects.all().order_by('username'), required=True, label='Recipient User')
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
        recipient = form.cleaned_data['recipient']
        subject = form.cleaned_data['subject'] or 'School Message'
        message_text = form.cleaned_data['message']
        send_email_opt = form.cleaned_data['send_email']
        send_sms_opt = form.cleaned_data['send_sms']
        if send_email_opt and recipient.email:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(subject, message_text, settings.DEFAULT_FROM_EMAIL, [recipient.email])
        if send_sms_opt:
            # Try to get phone from related profile (Teacher/Student), fallback to user.phone if exists
            phone = None
            if hasattr(recipient, 'teacher') and recipient.teacher.phone:
                phone = recipient.teacher.phone
            elif hasattr(recipient, 'student') and recipient.student.phone:
                phone = recipient.student.phone
            elif hasattr(recipient, 'phone') and recipient.phone:
                phone = recipient.phone
            if phone:
                from .messaging_utils import send_sms
                sms_success, sms_response = send_sms(phone, message_text)
                if not sms_success:
                    messages.error(request, f"SMS sending failed: {sms_response}")
                    return render(request, 'dashboards/admin_send_message.html', {'form': form, 'sms_error': sms_response, 'recipient': recipient})
            else:
                messages.error(request, f"Recipient '{recipient}' does not have a phone number assigned. Please update their contact information before sending an SMS.")
                return render(request, 'dashboards/admin_send_message.html', {'form': form, 'missing_phone': True, 'recipient': recipient})
        messages.success(request, 'Message sent successfully!')
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
