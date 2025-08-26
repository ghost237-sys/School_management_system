from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from core.models import User, Teacher, Student, Message, Class
from django.db.models import Q

@login_required
def teacher_messaging(request):
    # Only allow teachers
    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Only teachers can access this page.')
        return redirect('login')
    teacher = request.user.teacher
    # Determine if teacher is a class teacher
    class_groups = Class.objects.filter(class_teacher=teacher)
    recipients = []
    if class_groups.exists():
        # Class teacher: add all students in their class
        students = Student.objects.filter(class_group__in=class_groups)
        for s in students:
            if s.user:
                recipients.append({'id': s.user.id, 'name': s.full_name, 'role': 'student'})
    # Add all admin users to recipients
    admin_users = User.objects.filter(role='admin')
    for admin in admin_users:
        recipients.append({'id': admin.id, 'name': admin.get_full_name() or admin.username, 'role': 'admin'})
    # If not class teacher, only allow admin users
    if not class_groups.exists():
        recipients = []
        for admin in admin_users:
            recipients.append({'id': admin.id, 'name': admin.get_full_name() or admin.username, 'role': 'admin'})
    recipient_id = request.GET.get('recipient')
    selected_user = None
    for r in recipients:
        if str(r['id']) == str(recipient_id):
            selected_user = r
            break
    chat_history = []
    if selected_user:
        chat_history = Message.objects.filter(
            (Q(sender=request.user, recipient_id=selected_user['id']) | Q(sender_id=selected_user['id'], recipient=request.user))
        ).order_by('timestamp')
    # Handle sending message and email
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
        'teacher': teacher,
        'recipients': recipients,
        'selected_user': selected_user,
        'selected_recipient_id': recipient_id,
        'chat_history': chat_history,
    }
    return render(request, 'dashboards/teacher_messaging.html', context)
