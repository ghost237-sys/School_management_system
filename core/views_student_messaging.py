from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from core.models import User, Student, Message, Class
from django.db.models import Q

@login_required
def student_messaging(request):
    # Only allow students
    if not hasattr(request.user, 'student'):
        messages.error(request, 'Only students can access this page.')
        # Redirect to a safe generic dashboard instead of accessing request.user.student
        return redirect('admin_overview')
    student = request.user.student
    # Find admin user(s)
    admin_users = User.objects.filter(role='admin')
    admin_user = admin_users.first() if admin_users.exists() else None
    # Find class teacher
    class_teacher_user = None
    if getattr(student, 'class_group', None) and getattr(student.class_group, 'class_teacher', None):
        class_teacher_user = student.class_group.class_teacher.user
    # Find clerks (finance desk)
    clerk_users = User.objects.filter(role='clerk')
    # Recipients list
    recipients = []
    if admin_user:
        recipients.append({'id': admin_user.id, 'name': admin_user.get_full_name() or admin_user.username, 'role': 'admin'})
    if class_teacher_user:
        recipients.append({'id': class_teacher_user.id, 'name': class_teacher_user.get_full_name() or class_teacher_user.username, 'role': 'class teacher'})
    for c in clerk_users:
        recipients.append({'id': c.id, 'name': c.get_full_name() or c.username, 'role': 'clerk'})
    # Determine selected recipient
    recipient_id = request.GET.get('recipient')
    recipient_role = (request.GET.get('recipient_role') or '').strip().lower()
    selected_user = None
    # Prefer explicit id selection
    for r in recipients:
        if recipient_id and str(r['id']) == str(recipient_id):
            selected_user = r
            break
    # If role hint provided and no explicit id match, pick first by role
    if not selected_user and recipient_role:
        for r in recipients:
            if r.get('role','').lower() == recipient_role:
                selected_user = r
                break
    # Load chat history
    chat_history = []
    if selected_user:
        chat_history = Message.objects.filter(
            (Q(sender=request.user, recipient_id=selected_user['id']) | Q(sender_id=selected_user['id'], recipient=request.user))
        ).order_by('timestamp')
    # Handle sending message
    if request.method == 'POST' and selected_user:
        content = request.POST.get('message', '').strip()
        if content:
            msg = Message.objects.create(sender=request.user, recipient_id=selected_user['id'], content=content)
            # Send email if recipient has email
            recipient_user = User.objects.get(id=selected_user['id'])
            if recipient_user.email:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject="New Message from {}".format(request.user.get_full_name() or request.user.username),
                    message=content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_user.email],
                )
            return redirect(f'{request.path}?recipient={selected_user["id"]}')
    context = {
        'recipients': recipients,
        'selected_user': selected_user,
        'selected_recipient_id': recipient_id,
        'chat_history': chat_history,
    }
    return render(request, 'dashboards/student_messaging.html', context)
