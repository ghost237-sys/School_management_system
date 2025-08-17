from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q

from core.models import User, Message


def is_clerk(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'clerk'


@login_required
@user_passes_test(is_clerk)
def clerk_messaging(request):
    """
    Clerk messaging UI limited to Admins and Students only.
    - Sidebar lists Admins and Students (sorted by most recent conversation).
    - Chat view shows conversation with a selected recipient.
    - Clerk can send messages; email notification is sent if recipient has an email.
    """
    # Build recipients queryset
    recipients_qs = User.objects.filter(role__in=['admin', 'student']).only('id', 'first_name', 'last_name', 'username', 'role')

    # Sort by latest interaction time with current user
    def latest_msg_time(u: User):
        msg = Message.objects.filter(
            Q(sender=request.user, recipient=u) | Q(sender=u, recipient=request.user)
        ).order_by('-timestamp').first()
        return msg.timestamp if msg else None

    recipients = list(recipients_qs)
    recipients.sort(key=lambda u: latest_msg_time(u) or 0, reverse=True)

    # Determine selected recipient
    recipient_id = request.GET.get('recipient')
    selected_user = None
    if recipient_id:
        try:
            selected_user = next((u for u in recipients if str(u.id) == str(recipient_id)), None)
        except Exception:
            selected_user = None

    # Load chat history
    chat_history = []
    if selected_user:
        chat_qs = Message.objects.filter(
            Q(sender=request.user, recipient=selected_user) | Q(sender=selected_user, recipient=request.user)
        ).order_by('timestamp')
        chat_history = chat_qs

    # Handle sending message
    if request.method == 'POST' and selected_user:
        content = (request.POST.get('message') or '').strip()
        if not content:
            messages.error(request, 'Please enter a message to send.')
            return redirect(f"{request.path}?recipient={selected_user.id}")
        Message.objects.create(sender=request.user, recipient=selected_user, content=content)
        # Email notification (best-effort)
        if selected_user.email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject=f"New Message from {request.user.get_full_name() or request.user.username}",
                    message=content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[selected_user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
        return redirect(f"{request.path}?recipient={selected_user.id}")

    # Prepare recipients payload for template (id, name, role)
    recipients_list = [
        {
            'id': u.id,
            'name': (u.get_full_name() or u.username),
            'role': u.role,
        }
        for u in recipients
    ]

    context = {
        'recipients': recipients_list,
        'selected_user': (
            {'id': selected_user.id, 'name': selected_user.get_full_name() or selected_user.username, 'role': selected_user.role}
            if selected_user else None
        ),
        'selected_recipient_id': str(recipient_id) if recipient_id else '',
        'chat_history': chat_history,
    }
    return render(request, 'dashboards/clerk_messaging.html', context)
