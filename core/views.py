from django.shortcuts import render, redirect
from django.contrib.auth import login , authenticate
from .forms import CustomUserCreationForm, AddStudentForm, EditStudentClassForm, FeeCategoryForm, FeeAssignmentForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout
from django.contrib import messages
from .models import User, FeeCategory, FeeAssignment, FeePayment, Student, Class, Term, Exam, Grade, Teacher
from django.db.models import Q
from django.shortcuts import get_object_or_404


from django.utils import timezone
from datetime import datetime, time
from .models import Event

def create_event(title, date, end_date=None, all_day=True):
    """
    Create and store an event in the database.
    - title: Event title
    - date: date or datetime (for start)
    - end_date: date or datetime (optional)
    - all_day: bool
    """
    # Ensure start is timezone-aware datetime
    if isinstance(date, datetime):
        start_dt = timezone.make_aware(date) if timezone.is_naive(date) else date
    else:
        # If a date, combine with midnight
        start_dt = timezone.make_aware(datetime.combine(date, time.min))
    end_dt = None
    if end_date:
        if isinstance(end_date, datetime):
            end_dt = timezone.make_aware(end_date) if timezone.is_naive(end_date) else end_date
        else:
            end_dt = timezone.make_aware(datetime.combine(end_date, time.max))
    return Event.objects.create(title=title, start=start_dt, end=end_dt, all_day=all_day)

from .forms import EventForm
from django.http import JsonResponse

@login_required(login_url='login')
def exam_events_api(request):
    from .models import Exam
    events = []
    for exam in Exam.objects.all():
        events.append({
            'id': exam.id,
            'title': exam.name,
            'start': str(exam.date),
            'type': getattr(exam, 'type', ''),
            'level': getattr(exam, 'level', ''),
            'room': getattr(exam, 'room', ''),
        })
    return JsonResponse(events, safe=False)


@login_required(login_url='login')
def admin_events(request):
    """Admin Events Management Page: add, edit, delete events."""
    from django.contrib import messages
    filter_type = request.GET.get('filter', 'all')
    now = timezone.now()
    all_events = Event.objects.order_by('-start')
    if filter_type == 'upcoming':
        filtered_events = all_events.filter(start__gte=now)
    elif filter_type == 'done':
        filtered_events = all_events.filter(is_done=True)
    elif filter_type == 'undone':
        filtered_events = all_events.filter(((Q(end__lt=now) | (Q(end__isnull=True) & Q(start__lt=now))) & Q(is_done=False)))
    else:
        filtered_events = all_events
    event_id = request.GET.get('edit')
    delete_id = request.GET.get('delete')
    form = None
    edit_event = None

    # Delete event
    if delete_id:
        try:
            event = Event.objects.get(id=delete_id)
            event.delete()
            messages.success(request, 'Event deleted successfully.')
            return redirect('admin_events')
        except Event.DoesNotExist:
            messages.error(request, 'Event not found.')
            return redirect('admin_events')

    # Edit event
    if event_id:
        try:
            edit_event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            messages.error(request, 'Event not found.')
            return redirect('admin_events')
        form = EventForm(request.POST or None, instance=edit_event)
    else:
        form = EventForm(request.POST or None)

    # Mark event as done with comment
    if request.method == 'POST' and 'mark_done_event_id' in request.POST:
        try:
            event = Event.objects.get(id=request.POST['mark_done_event_id'])
            event.is_done = 'is_done' in request.POST
            event.comment = request.POST.get('comment', '')
            event.save()
            messages.success(request, 'Event status updated.')
            return redirect('admin_events')
        except Event.DoesNotExist:
            messages.error(request, 'Event not found.')
            return redirect('admin_events')

    # Add or update event
    if request.method == 'POST' and 'mark_done_event_id' not in request.POST:
        if form.is_valid():
            form.save()
            if edit_event:
                messages.success(request, 'Event updated successfully!')
            else:
                messages.success(request, 'Event created successfully!')
            return redirect('admin_events')
        else:
            messages.error(request, 'Please correct the errors below.')

    # Determine which events have passed and are not done
    now = timezone.now()
    past_events = [e for e in all_events if ((e.end and e.end < now) or (not e.end and e.start < now)) and not e.is_done]

    return render(request, 'dashboards/admin_events.html', {
        'form': form,
        'all_events': all_events,
        'filtered_events': filtered_events,
        'edit_event': edit_event,
        'past_events': past_events,
        'filter_type': filter_type,
    })

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email')


# def register_view(request):
#     # Disabled: Only admin can create users
#     return redirect('login')



@login_required(login_url='login')
def dashboard(request):
    # Redirect admin to overview, others to their dashboards
    if request.user.role == 'admin':
        from .models import Event
        events = Event.objects.order_by('start')
        from django.urls import reverse
        # You may want to aggregate other dashboard data as before, but now add 'events' to context
        return render(request, 'dashboards/admin_dashboard.html', {'events': events})
    elif request.user.role == 'teacher':
        return redirect('teacher_dashboard', teacher_id=request.user.teacher.id)
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    else:
        from django.contrib import messages
        messages.error(request, 'Unknown user role. Please contact admin.')
        return redirect('login')

# Student/Parent Fee Dashboard View
from django.db.models import Sum
from .models import FeeAssignment, FeePayment, Term, Student
from django.shortcuts import get_object_or_404

@login_required(login_url='login')
def admin_payment(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    students = Student.objects.select_related('user').all()
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        amount_paid = request.POST.get('amount_paid')
        payment_method = request.POST.get('payment_method')
        reference = request.POST.get('reference')
        student = get_object_or_404(Student, id=student_id)
        # Get current term
        current_term = Term.objects.order_by('-start_date').first()
        # Get all fee assignments for this student for the current term
        fee_assignments = []
        if student.class_group and current_term:
            assignments = FeeAssignment.objects.filter(class_group=student.class_group, term=current_term)
            for assignment in assignments:
                paid = FeePayment.objects.filter(student=student, fee_assignment=assignment).aggregate(total=Sum('amount_paid'))['total'] or 0
                fee_assignments.append({
                    'id': assignment.id,
                    'fee_category': assignment.fee_category,
                    'amount': assignment.amount,
                    'paid': paid,
                    'outstanding': max(assignment.amount - paid, 0),
                })
        # Distribute payment across unpaid assignments (oldest first)
        if amount_paid:
            remaining = float(amount_paid)
            for assignment in fee_assignments:
                outstanding = float(assignment['outstanding'])
                if outstanding <= 0:
                    continue
                pay = min(remaining, outstanding)
                if pay > 0:
                    FeePayment.objects.create(
                        student=student,
                        fee_assignment=FeeAssignment.objects.get(id=assignment['id']),
                        amount_paid=pay,
                        payment_method=payment_method,
                        reference=reference
                    )
                    remaining -= pay
                if remaining <= 0:
                    break
            messages.success(request, 'Payment recorded successfully!')
            return redirect('admin_payment')
    context = {
        'students': students,
    }
    return render(request, 'dashboards/admin_payment.html', context)


@login_required(login_url='login')
def student_fees(request):
    # Get the logged-in user's student profile
    student = get_object_or_404(Student, user=request.user)
    # Get current term (latest by start date)
    current_term = Term.objects.order_by('-start_date').first()
    fee_assignments = []
    if student.class_group and current_term:
        assignments = FeeAssignment.objects.filter(class_group=student.class_group, term=current_term)
        for assignment in assignments:
            paid = FeePayment.objects.filter(student=student, fee_assignment=assignment).aggregate(total=Sum('amount_paid'))['total'] or 0
            fee_assignments.append({
                'id': assignment.id,
                'fee_category': assignment.fee_category,
                'amount': assignment.amount,
                'paid': paid,
                'outstanding': max(assignment.amount - paid, 0),
            })
    # Payment history
    fee_payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
    # Handle payment submission
    if request.method == 'POST':
        amount_paid = request.POST.get('amount_paid')
        payment_method = request.POST.get('payment_method')
        reference = request.POST.get('reference')
        if amount_paid:
            # Distribute payment across unpaid assignments (oldest first)
            remaining = float(amount_paid)
            for assignment in fee_assignments:
                outstanding = float(assignment['outstanding'])
                if outstanding <= 0:
                    continue
                pay = min(remaining, outstanding)
                if pay > 0:
                    FeePayment.objects.create(
                        student=student,
                        fee_assignment=FeeAssignment.objects.get(id=assignment['id']),
                        amount_paid=pay,
                        payment_method=payment_method,
                        reference=reference
                    )
                    remaining -= pay
                if remaining <= 0:
                    break
            messages.success(request, 'Payment recorded successfully!')
            return redirect('student_fees')
    context = {
        'fee_assignments': fee_assignments,
        'fee_payments': fee_payments,
        'current_term': current_term,
    }
    return render(request, 'dashboards/student_fees.html', context)

# Admin Fees Management View
@login_required(login_url='login')
def admin_fees(request):
    if request.user.role != 'admin':
        return redirect('dashboard')

    # Forms for fee category and assignment
    fee_form = FeeCategoryForm(request.POST or None, prefix='fee')
    assign_form = FeeAssignmentForm(request.POST or None, prefix='assign')

    # Handle form submissions
    if request.method == 'POST':
        if 'fee-name' in request.POST:  # FeeCategoryForm
            if fee_form.is_valid():
                fee_form.save()
                messages.success(request, 'Fee category saved.')
                return redirect('admin_fees')
        elif 'assign-fee_category' in request.POST:  # FeeAssignmentForm
            if assign_form.is_valid():
                assign_form.save()
                messages.success(request, 'Fee assigned to class/term.')
                return redirect('admin_fees')

    # Fees overview
    # Get current term (by date range)
    today = timezone.now().date()
    current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.filter(start_date__lte=today, end_date__isnull=True).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.order_by('-start_date').first()
    if current_term:
        fees = FeeAssignment.objects.select_related('fee_category', 'class_group', 'term').filter(term=current_term)
    else:
        fees = FeeAssignment.objects.none()
    
    # Student assignments overview
    assignments = []
    student_totals = {}
    student_category_totals = {}
    
    if current_term:
        # Find all terms up to and including the current term
        terms_up_to_current = Term.objects.filter(start_date__lte=current_term.start_date)
        
        all_fee_categories = FeeCategory.objects.all()
        all_students = Student.objects.all()
        
        for student in all_students:
            if student.class_group:
                # All assignments for this student/class up to the current term
                assignments_for_student = FeeAssignment.objects.filter(
                    class_group=student.class_group, 
                    term__in=terms_up_to_current
                )
                student_totals[student.id] = sum(a.amount for a in assignments_for_student)
                
                # Group totals by category
                category_totals = {}
                for cat in all_fee_categories:
                    cat_assignments = assignments_for_student.filter(fee_category=cat)
                    category_totals[cat.id] = sum(a.amount for a in cat_assignments)
                student_category_totals[student.id] = category_totals
    
    if current_term:
        assignments = []
        for assignment in FeeAssignment.objects.select_related('class_group', 'term', 'fee_category').filter(term=current_term):
            if assignment.class_group:
                classes_at_level = Class.objects.filter(level=assignment.class_group.level)
                students = Student.objects.filter(class_group__in=classes_at_level)
                for student in students:
                    paid = FeePayment.objects.filter(student=student, fee_assignment=assignment).aggregate(total=Sum('amount_paid'))['total'] or 0
                    is_paid = paid >= assignment.amount
                    balance = assignment.amount - paid
                    assignments.append({
                        'student': student,
                        'fee': assignment,
                        'paid': paid,
                        'balance': balance,
                    })

    # Calculate total paid per student
    student_paid = {}
    for student in all_students:
        if student.class_group and current_term:
            # Sum all payments made by the student up to and including the current term
            payments = FeePayment.objects.filter(
                student=student, 
                fee_assignment__term__start_date__lte=current_term.start_date
            )
            student_paid[student.id] = sum(p.amount_paid for p in payments)
    # Calculate balance per student
    student_balances = {sid: student_totals.get(sid, 0) - student_paid.get(sid, 0) for sid in student_totals}
    
    # Class filter
    all_classes = Class.objects.all()
    selected_class_id = request.GET.get('class_group')
    if selected_class_id:
        filtered_students = all_students.filter(class_group_id=selected_class_id)
    else:
        filtered_students = all_students
    
    # Sorting functionality
    sort_order = request.GET.get('sort', 'largest')
    students_with_balance = list(filtered_students)
    students_with_balance.sort(key=lambda s: student_balances.get(s.id, 0), reverse=(sort_order == 'largest'))
    
    # Prepare data for pie chart (fee category distribution)
    category_data = []
    category_labels = []
    if current_term:
        for cat in all_fee_categories:
            total = sum(student_category_totals.get(s.id, {}).get(cat.id, 0) for s in students_with_balance)
            if total > 0:  # Only include categories with data
                category_data.append(total)
                category_labels.append(cat.name)

    # Prepare data for line graph (payments over time)
    payment_data = []
    payment_labels = []
    from collections import defaultdict
    monthly_totals = defaultdict(float)
    
    if current_term:
        # Get all payments up to the current term
        payments = FeePayment.objects.filter(
            fee_assignment__term__start_date__lte=current_term.start_date
        ).order_by('payment_date')
        
        # Group payments by month
        for payment in payments:
            month_key = payment.payment_date.strftime('%Y-%m')
            monthly_totals[month_key] += float(payment.amount_paid)
        
        # Sort by date and prepare data
        for month in sorted(monthly_totals.keys()):
            payment_labels.append(month)
            payment_data.append(monthly_totals[month])

    context = {
        'fee_form': fee_form,
        'assign_form': assign_form,
        'fees': fees,
        'assignments': assignments,
        'student_totals': student_totals,
        'student_category_totals': student_category_totals,
        'all_students': students_with_balance,
        'all_fee_categories': all_fee_categories,
        'student_balances': student_balances,
        'student_paid': student_paid,
        'all_classes': all_classes,
        'selected_class_id': selected_class_id,
        'sort_order': sort_order,
        'current_term': current_term,
        'category_data': category_data,
        'category_labels': category_labels,
        'payment_data': payment_data,
        'payment_labels': payment_labels,
    }
    return render(request, 'dashboards/admin_fees.html', context)

# Admin Overview View
@login_required(login_url='login')
def admin_overview(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Student, Grade, Subject, Class, Teacher, Exam, Attendance, AcademicYear, Term
    from django.db.models import Avg, Q
    import datetime

    # Filters
    selected_class_id = request.GET.get('class', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    classes = Class.objects.all()
    students_qs = Student.objects.all()
    grades_qs = Grade.objects.all()

    # Filter by class
    if selected_class_id:
        students_qs = students_qs.filter(class_group_id=selected_class_id)
        grades_qs = grades_qs.filter(student__class_group_id=selected_class_id)
    # Filter by date range (filter grades by exam date)
    if start_date:
        try:
            start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            grades_qs = grades_qs.filter(exam__date__gte=start_dt)
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            grades_qs = grades_qs.filter(exam__date__lte=end_dt)
        except Exception:
            pass

    # Total students (after filter)
    total_students = students_qs.count()

    # Incomplete profiles
    incomplete_profiles = Student.objects.filter(Q(user__first_name='') | Q(user__last_name='')).count()

    # Overall average score (after filter)
    average_score = grades_qs.aggregate(avg=Avg('score'))['avg'] or 0

    # Attendance rate (set to N/A unless Attendance model is present)
    attendance_rate = 'N/A'
    # Uncomment and adjust below if you have an Attendance model:
    # from .models import Attendance
    # attendance_qs = Attendance.objects.all()
    # if selected_class_id:
    #     attendance_qs = attendance_qs.filter(student__class_group_id=selected_class_id)
    # if start_date:
    #     attendance_qs = attendance_qs.filter(date__gte=start_dt)
    # if end_date:
    #     attendance_qs = attendance_qs.filter(date__lte=end_dt)
    # total_attendance = attendance_qs.count()
    # present_count = attendance_qs.filter(status='present').count()
    # attendance_rate = round((present_count / total_attendance) * 100, 2) if total_attendance else 'N/A'

    # Subject averages (after filter)
    subject_averages = (
        grades_qs.values('subject__name')
        .annotate(avg_score=Avg('score'))
        .order_by('-avg_score')
    )
    # Prepare as list of dicts: subject, avg_score
    subject_averages_list = [
        {'subject': s['subject__name'], 'avg_score': s['avg_score']} for s in subject_averages if s['avg_score'] is not None
    ]

    # New summary stats
    total_teachers = Teacher.objects.count()
    total_classes = Class.objects.count()
    total_subjects = Subject.objects.count()
    # Current academic term/week (basic)
    # --- Use same logic as admin_academic_years to determine current_term ---
    import datetime
    today = datetime.date.today()
    all_years = AcademicYear.objects.prefetch_related('terms').all().order_by('-year')
    academic_years = []
    for year in all_years:
        terms = year.terms.all()
        if any(term.end_date and term.end_date >= today for term in terms):
            academic_years.append(year)
    current_term = None
    current_year = None
    for year in academic_years:
        terms = sorted(year.terms.all(), key=lambda t: t.start_date or datetime.date.min)
        for term in terms:
            if term.start_date and term.end_date:
                if term.start_date <= today <= term.end_date:
                    current_term = term
                    current_year = year
                    break
        if current_term:
            break
    # Fee summary (mock/sample)
    fee_summary = {
        'total_due': 1000000,
        'total_paid': 750000,
        'balance': 250000,
        'collection_rate': 75,
    }
    # Upcoming events (real)
    from .models import Event
    from django.utils import timezone
    now = timezone.now()
    upcoming_events = Event.objects.filter(start__gte=now).order_by('start')

    # Alerts & notifications (mock/sample)
    alerts = [
        {'type': 'danger', 'msg': 'Overdue fees for 12 students.'},
        {'type': 'warning', 'msg': 'Low attendance in Class 3B.'},
        {'type': 'info', 'msg': '2 teachers have not uploaded marks.'},
        {'type': 'danger', 'msg': 'Conflicting teacher assignments detected.'},
    ]
    # Recent activity logs (mock/sample)
    activity_logs = [
        {'time': '08:30', 'desc': 'Teacher John logged in.'},
        {'time': '08:35', 'desc': 'Marks uploaded for Class 2A.'},
        {'time': '08:40', 'desc': 'New student Mary W. added.'},
        {'time': '08:45', 'desc': 'Profile updated: Teacher Jane.'},
    ]
    # Quick actions (links)
    quick_actions = [
        {'label': 'Add Student', 'url': 'admin_students'},
        {'label': 'Add Teacher', 'url': 'admin_teachers'},
        {'label': 'Assign Subjects', 'url': 'admin_teachers'},
        {'label': 'Upload Marks', 'url': 'admin_exams'},
        {'label': 'Generate Reports', 'url': 'admin_analytics'},
        {'label': 'Manage Timetable', 'url': '#'},
    ]
    context = {
        'total_students': total_students,
        'average_score': average_score,
        'attendance_rate': attendance_rate,
        'subject_averages': subject_averages_list,
        'classes': classes,
        'selected_class_id': int(selected_class_id) if selected_class_id else '',
        'start_date': start_date,
        'end_date': end_date,
        'incomplete_profiles': incomplete_profiles,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'current_term': current_term,
        'current_year': current_year,
        'fee_summary': fee_summary,
        'upcoming_events': upcoming_events,
        'alerts': alerts,
        'activity_logs': activity_logs,
        'quick_actions': quick_actions,
    }
    return render(request, 'dashboards/admin_overview.html', context)


from django.http import JsonResponse
from django.template.loader import render_to_string
from .forms import AddTeacherForm, AddStudentForm, AddClassForm, AddSubjectForm, EditTermDatesForm

from django.shortcuts import get_object_or_404

@login_required(login_url='login')
def add_student_ajax(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == 'POST':
        form = AddStudentForm(request.POST)
        if form.is_valid():
            # Save user and student
            user = form.save_user() if hasattr(form, 'save_user') else None
            student = form.save(commit=False)
            if user:
                student.user = user
            student.save()
            return JsonResponse({'success': True})
        else:
            html = render_to_string('partials/add_student_form.html', {'form': form}, request=request)
            return JsonResponse({'success': False, 'form_html': html})
    else:
        form = AddStudentForm()
        html = render_to_string('partials/add_student_form.html', {'form': form}, request=request)
        return JsonResponse({'form_html': html})

@login_required(login_url='login')
def add_teacher_ajax(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            user = form.save_user() if hasattr(form, 'save_user') else None
            teacher = form.save(commit=False)
            if user:
                teacher.user = user
            teacher.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            return JsonResponse({'success': True})
        else:
            html = render_to_string('partials/add_teacher_form.html', {'form': form}, request=request)
            return JsonResponse({'success': False, 'form_html': html})
    else:
        form = AddTeacherForm()
        html = render_to_string('partials/add_teacher_form.html', {'form': form}, request=request)
        return JsonResponse({'form_html': html})

@login_required(login_url='login')
def add_class_ajax(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == 'POST':
        form = AddClassForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            html = render_to_string('partials/add_class_form.html', {'form': form}, request=request)
            return JsonResponse({'success': False, 'form_html': html})
    else:
        form = AddClassForm()
        html = render_to_string('partials/add_class_form.html', {'form': form}, request=request)
        return JsonResponse({'form_html': html})

@login_required(login_url='login')
def add_subject_ajax(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == 'POST':
        form = AddSubjectForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            html = render_to_string('partials/add_subject_form.html', {'form': form}, request=request)
            return JsonResponse({'success': False, 'form_html': html})
    else:
        form = AddSubjectForm()
        html = render_to_string('partials/add_subject_form.html', {'form': form}, request=request)
        return JsonResponse({'form_html': html})

# FullCalendar Event AJAX Views
from .models import Event
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime

@login_required(login_url='login')
def events_feed(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    events = Event.objects.all()
    data = [
        {
            'id': e.id,
            'title': e.title,
            'start': e.start.isoformat(),
            'end': e.end.isoformat() if e.end else None,
            'allDay': e.all_day,
        } for e in events
    ]
    return JsonResponse(data, safe=False)

@login_required(login_url='login')
@require_POST
def event_create(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    title = request.POST.get('title', '').strip()
    start = parse_datetime(request.POST.get('start', ''))
    end = parse_datetime(request.POST.get('end', '')) if request.POST.get('end') else None
    all_day = request.POST.get('allDay', 'false') == 'true'
    if not title or not start:
        return JsonResponse({'error': 'Title and start required.'}, status=400)
    event = Event.objects.create(title=title, start=start, end=end, all_day=all_day)
    return JsonResponse({'success': True, 'id': event.id})

@login_required(login_url='login')
@require_POST
def event_update(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    event_id = request.POST.get('id')
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found.'}, status=404)
    event.title = request.POST.get('title', event.title)
    event.start = parse_datetime(request.POST.get('start', event.start.isoformat()))
    event.end = parse_datetime(request.POST.get('end', '')) if request.POST.get('end') else None
    event.all_day = request.POST.get('allDay', 'false') == 'true'
    event.save()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@require_POST
def event_delete(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    event_id = request.POST.get('id')
    try:
        event = Event.objects.get(id=event_id)
        event.delete()
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found.'}, status=404)
    return JsonResponse({'success': True})

# FullCalendar AJAX Event Views
from .models import Event
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

@login_required(login_url='login')
def events_json(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    events = Event.objects.all()
    data = [{
        'id': event.id,
        'title': event.title,
        'start': event.start.isoformat(),
        'end': event.end.isoformat() if event.end else None,
        'allDay': event.all_day,
    } for event in events]
    return JsonResponse(data, safe=False)

@login_required(login_url='login')
@require_POST
@csrf_exempt
def event_create(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    title = request.POST.get('title', '').strip()
    start = request.POST.get('start')
    end = request.POST.get('end')
    all_day = request.POST.get('allDay') == 'true'
    if not title or not start:
        return JsonResponse({'error': 'Title and start required.'}, status=400)
    event = Event.objects.create(title=title, start=start, end=end or None, all_day=all_day)
    return JsonResponse({'success': True, 'id': event.id})

@login_required(login_url='login')
@require_POST
@csrf_exempt
def event_update(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    event_id = request.POST.get('id')
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found.'}, status=404)
    event.title = request.POST.get('title', event.title)
    event.start = request.POST.get('start', event.start)
    event.end = request.POST.get('end', event.end)
    event.all_day = request.POST.get('allDay') == 'true'
    event.save()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@require_POST
@csrf_exempt
def event_delete(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    event_id = request.POST.get('id')
    try:
        event = Event.objects.get(id=event_id)
        event.delete()
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found.'}, status=404)
    return JsonResponse({'success': True})

# Admin Teachers View

@login_required(login_url='login')
def admin_teachers(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Teacher, Department, Subject, User, Class
    from django.db.models import Q
    teachers = Teacher.objects.select_related('user', 'department').prefetch_related('subjects', 'teacherclassassignment_set__class_group').all()
    departments = Department.objects.all()
    subjects = Subject.objects.all()
    classes = Class.objects.select_related('class_teacher').all()
    form = AddTeacherForm()

    # Handle Add Teacher POST
    if request.method == 'POST' and 'add_teacher' in request.POST:
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            # Create User
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role='teacher',
            )
            # Create Teacher
            teacher = Teacher.objects.create(
                user=user,
                tsc_number=form.cleaned_data['tsc_number'],
                staff_id=form.cleaned_data['staff_id'],
                phone=form.cleaned_data['phone'],
                gender=form.cleaned_data['gender'],
                department=form.cleaned_data['department'],
            )
            teacher.subjects.set(form.cleaned_data['subjects'])
            teacher.save()
            return redirect('admin_teachers')

    # Filtering
    search = request.GET.get('search', '').strip()
    department_id = request.GET.get('department', '')
    subject_id = request.GET.get('subject', '')
    gender = request.GET.get('gender', '')

    if search:
        teachers = teachers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone__icontains=search) |
            Q(tsc_number__icontains=search) |
            Q(staff_id__icontains=search)
        )
    if department_id:
        teachers = teachers.filter(department_id=department_id)
    if subject_id:
        teachers = teachers.filter(subjects__id=subject_id)
    if gender:
        teachers = teachers.filter(gender=gender)
    teachers = teachers.distinct()

    context = {
        'teachers': teachers,
        'departments': departments,
        'subjects': subjects,
        'add_teacher_form': form,
    }
    return render(request, 'dashboards/admin_teachers.html', context)


@login_required(login_url='login')
def edit_teacher(request, teacher_id):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Teacher, User
    teacher = get_object_or_404(Teacher, id=teacher_id)
    user = teacher.user
    if request.method == 'POST':
        form = AddTeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            # Update user fields
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            if 'password' in form.cleaned_data and form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.save()
            # Update teacher fields
            teacher.tsc_number = form.cleaned_data['tsc_number']
            teacher.staff_id = form.cleaned_data['staff_id']
            teacher.phone = form.cleaned_data['phone']
            teacher.gender = form.cleaned_data['gender']
            teacher.department = form.cleaned_data['department']
            teacher.subjects.set(form.cleaned_data['subjects'])
            teacher.save()

            # Handle class_teacher_of assignments
            from .models import Class
            selected_classes = form.cleaned_data.get('class_teacher_of', [])
            # Remove this teacher as class_teacher from classes not selected
            Class.objects.filter(class_teacher=teacher).exclude(id__in=[c.id for c in selected_classes]).update(class_teacher=None)
            # Assign this teacher as class_teacher for selected classes
            for c in selected_classes:
                c.class_teacher = teacher
                c.save()

            messages.success(request, 'Teacher updated successfully.')
            return redirect('admin_teachers')
    else:
        form = AddTeacherForm(instance=teacher, initial={
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })
    return render(request, 'dashboards/edit_teacher.html', {'form': form, 'teacher': teacher})


@login_required(login_url='login')
def delete_teacher(request, teacher_id):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Teacher, User, Class
    teacher = get_object_or_404(Teacher, id=teacher_id)
    user = teacher.user
    if request.method == 'POST':
        # Unassign teacher from any classes where they are class_teacher
        Class.objects.filter(class_teacher=teacher).update(class_teacher=None)
        user.delete()
        messages.success(request, 'Teacher deleted successfully.')
        return redirect('admin_teachers')
    return render(request, 'dashboards/delete_teacher.html', {'teacher': teacher})


# Student Profile View
@login_required(login_url='login')

def student_profile(request, student_id):
    from .models import Student, Class, Teacher
    from django.shortcuts import get_object_or_404
    student = get_object_or_404(Student, id=student_id)
    # Only allow admin, the student themselves, or their class teacher
    is_admin = request.user.role == 'admin'
    is_student = hasattr(request.user, 'student') and request.user.student.id == student.id
    is_class_teacher = False
    if student.class_group and hasattr(request.user, 'teacher'):
        is_class_teacher = (student.class_group.class_teacher_id == request.user.teacher.id)
    if not (is_admin or is_student or is_class_teacher):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('You do not have permission to view this student profile.')

    # Handle class change
    if request.method == 'POST' and 'edit_class_group' in request.POST:
        form = EditStudentClassForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, "Class updated successfully.")
            return redirect('student_profile', student_id=student.id)
    else:
        form = EditStudentClassForm(instance=student)

    # --- Fee status for this student ---
    from .models import FeeAssignment, FeePayment, Term
    from django.db.models import Sum
    today = timezone.now().date()
    current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.filter(start_date__lte=today, end_date__isnull=True).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.order_by('-start_date').first()
    fee_assignments = []
    if student.class_group and current_term:
        # All assignments up to and including the current term (by start_date)
        assignments = FeeAssignment.objects.filter(class_group=student.class_group, term__start_date__lte=current_term.start_date)
        for assignment in assignments:
            paid = FeePayment.objects.filter(student=student, fee_assignment=assignment).aggregate(total=Sum('amount_paid'))['total'] or 0
            fee_assignments.append({
                'id': assignment.id,
                'fee_category': assignment.fee_category,
                'amount': assignment.amount,
                'paid': paid,
                'outstanding': max(assignment.amount - paid, 0),
            })
    fee_payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
    total_billed = sum(a['amount'] for a in fee_assignments)
    return render(request, 'dashboards/student_profile.html', {
        'student': student,
        'edit_class_form': form,
        'fee_assignments': fee_assignments,
        'fee_payments': fee_payments,
        'current_term': current_term,
        'total_billed': total_billed,
    })

# Teacher Profile View
@login_required(login_url='login')
def teacher_profile(request, teacher_id):
    from .models import Teacher
    from django.shortcuts import get_object_or_404
    teacher = get_object_or_404(Teacher, id=teacher_id)
    # Only allow admin or the teacher themselves
    if not (request.user.role == 'admin' or request.user.id == teacher.user.id):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('You do not have permission to view this profile.')
    return render(request, 'dashboards/teacher_profile.html', {'teacher': teacher})

# Teacher Dashboard View
@login_required(login_url='login')
def teacher_dashboard(request, teacher_id):
    from .models import Teacher, TeacherClassAssignment, Student, Grade
    from django.shortcuts import get_object_or_404
    from django.db.models import Avg

    teacher = get_object_or_404(Teacher.objects.select_related('user'), id=teacher_id)

    # Get all classes where the teacher teaches (via TeacherClassAssignment) or is class_teacher
    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group', 'subject')
    assigned_classes = set()
    # Prepare class_cards for dashboard cards (one per class+subject assignment)
    class_cards = []
    notifications = []
    greeting_name = f"Mr. {teacher.user.last_name}" if teacher.user.last_name else teacher.user.get_full_name() or teacher.user.username
    teacher_subjects = list(teacher.subjects.values_list('name', flat=True))
    # We'll collect classes from both assignments and class_teacher role, avoiding duplicates
    for assign in assignments:
        class_id = assign.class_group.id
        assigned_classes.add(class_id)
        students = Student.objects.filter(class_group=assign.class_group)
        student_count = students.count()
        grades = Grade.objects.filter(student__in=students, subject=assign.subject)
        avg_score = grades.aggregate(avg=Avg('score'))['avg']
        exams_marked = grades.values('exam').distinct().count()
        from .models import Exam
        total_exams = Exam.objects.filter(subject=assign.subject, class_group=assign.class_group).count() if hasattr(Exam, 'class_group') else Exam.objects.filter(subject=assign.subject).count()
        low_performers = grades.filter(score__lt=50).count()
        below_avg_count = grades.filter(score__lt=avg_score if avg_score else 50).count() if avg_score else 0
        if below_avg_count > 0:
            notifications.append(f"{below_avg_count} student{'s' if below_avg_count > 1 else ''} have dropped below average in {assign.subject.name} ({assign.class_group.name})")
        class_cards.append({
            'class_group': assign.class_group,
            'subject': assign.subject,
            'is_class_teacher': assign.class_group.class_teacher_id == teacher.id,
            'student_count': student_count,
            'avg_score': avg_score,
            'exams_marked': exams_marked,
            'total_exams': total_exams,
            'low_performers': low_performers,
        })
    # Now add classes where teacher is class_teacher but not in TeacherClassAssignment
    from .models import Class
    extra_classes = Class.objects.filter(class_teacher=teacher).exclude(id__in=assigned_classes)
    for class_obj in extra_classes:
        students = Student.objects.filter(class_group=class_obj)
        student_count = students.count()
        class_cards.append({
            'class_group': class_obj,
            'subject': None,
            'is_class_teacher': True,
            'student_count': student_count,
            'avg_score': None,
            'exams_marked': 0,
            'total_exams': 0,
            'low_performers': 0,
        })
    # teacher_classes for summary panel: all unique class names
    teacher_classes = list(set([c['class_group'].name for c in class_cards]))
    # Remove legacy/duplicate class_details/extra_classes logic (all cards come from class_cards now)


    # Placeholder for upcoming deadlines
    upcoming_deadlines = []

    context = {
        'teacher': teacher,
        'greeting_name': greeting_name,
        'teacher_subjects': teacher_subjects,
        'teacher_classes': teacher_classes,
        'notifications': notifications,
        'class_cards': class_cards,
        'upcoming_deadlines': upcoming_deadlines,
    }
    return render(request, 'dashboards/teacher_dashboard.html', context)


@login_required(login_url='login')
def manage_attendance(request, teacher_id):
    from .models import Teacher, TeacherClassAssignment
    from django.shortcuts import get_object_or_404

    teacher = get_object_or_404(Teacher.objects.select_related('user'), id=teacher_id)
    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group', 'subject')

    context = {
        'teacher': teacher,
        'assignments': assignments,
    }
    return render(request, 'dashboards/manage_attendance.html', context)


@login_required(login_url='login')
def take_attendance(request, teacher_id, class_id, subject_id):
    from .models import Teacher, Class, Subject, Student, Attendance
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    import datetime

    teacher = get_object_or_404(Teacher, id=teacher_id)
    class_group = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    students = Student.objects.filter(class_group=class_group).order_by('user__last_name', 'user__first_name')
    
    # Use today's date for attendance
    today = timezone.now().date()

    if request.method == 'POST':
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    subject=subject,
                    date=today,
                    defaults={
                        'teacher': teacher,
                        'class_group': class_group,
                        'status': status
                    }
                )
        messages.success(request, f"Attendance for {class_group.name} - {subject.name} has been saved.")
        return redirect('manage_attendance', teacher_id=teacher.id)

    # Get existing attendance records for today to pre-fill the form
    existing_attendance = Attendance.objects.filter(class_group=class_group, subject=subject, date=today)
    attendance_map = {att.student_id: att.status for att in existing_attendance}

    context = {
        'teacher': teacher,
        'class_group': class_group,
        'subject': subject,
        'students': students,
        'attendance_map': attendance_map,
        'today': today,
    }
    return render(request, 'dashboards/take_attendance.html', context)


@login_required(login_url='login')
def manage_grades(request, teacher_id):
    from .models import Teacher, TeacherClassAssignment, Student, Exam
    from django.shortcuts import get_object_or_404

    teacher = get_object_or_404(Teacher.objects.select_related('user'), id=teacher_id)
    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group', 'subject')
    assigned_classes = set()
    class_cards = []
    processed_pairs = set()

    # 1. Get explicit assignments from TeacherClassAssignment
    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group', 'subject')
    for assign in assignments:
        if assign.class_group and assign.subject:
            students = Student.objects.filter(class_group=assign.class_group).select_related('user').order_by('user__last_name', 'user__first_name')
            class_cards.append({
                'class_group': assign.class_group,
                'subject': assign.subject,
                'is_class_teacher': assign.class_group.class_teacher_id == teacher.id,
                'students': students,
            })
            processed_pairs.add((assign.class_group.id, assign.subject.id))

    # 2. For all subjects the teacher teaches, create cards for classes they are class teacher of, if not already processed
    from .models import Class
    classes_as_class_teacher = Class.objects.filter(class_teacher=teacher)
    all_subjects_taught = teacher.subjects.all()

    for subject in all_subjects_taught:
        for class_obj in classes_as_class_teacher:
            if (class_obj.id, subject.id) not in processed_pairs:
                students = Student.objects.filter(class_group=class_obj).select_related('user').order_by('user__last_name', 'user__first_name')
                class_cards.append({
                    'class_group': class_obj,
                    'subject': subject,
                    'is_class_teacher': True,
                    'students': students,
                })
                processed_pairs.add((class_obj.id, subject.id))

    # Group cards by subject
    from collections import defaultdict
    subject_cards = defaultdict(list)
    no_subject = []
    for card in class_cards:
        if card['subject']:
            subject_cards[card['subject'].name].append(card)
        else:
            no_subject.append(card)

    exams = Exam.objects.all()

    context = {
        'teacher': teacher,
        'subject_cards': dict(subject_cards),
        'no_subject': no_subject,
        'exams': exams,
    }
    return render(request, 'dashboards/manage_grades.html', context)



@login_required(login_url='login')
def input_grades(request, teacher_id, class_id, subject_id):
    from .models import Teacher, Class, Subject, Student, Exam, Grade, Term
    from django.shortcuts import get_object_or_404, redirect
    from .forms import GradeInputForm
    import datetime

    teacher = get_object_or_404(Teacher, id=teacher_id)
    class_group = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Get exam from GET param
    selected_exam = None
    exam_id = request.GET.get('exam_id')
    if exam_id:
        selected_exam = get_object_or_404(Exam, id=exam_id)

    # Handle POST request for saving grades or creating a new exam
    if request.method == 'POST':
        # Handle creating a new exam
        if 'create_exam' in request.POST:
            new_exam_name = request.POST.get('new_exam_name')
            term_id = request.POST.get('term')
            if new_exam_name and term_id:
                term = get_object_or_404(Term, id=term_id)
                exam, created = Exam.objects.get_or_create(
                    name=new_exam_name, 
                    term=term,
                    defaults={'date': datetime.date.today()}
                )
                if created:
                    messages.success(request, f'Successfully created exam "{exam.name}".')
                else:
                    messages.info(request, f'Exam "{exam.name}" already exists.')
                return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                              class_id=class_id, subject_id=subject_id, exam_id=exam.id)
        
        # Handle saving grades
        elif 'save_grades' in request.POST and selected_exam:
            students = Student.objects.filter(class_group=class_group)
            for student in students:
                score = request.POST.get(f'score_{student.id}')
                remarks = request.POST.get(f'remarks_{student.id}')
                if score and score.strip():
                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        exam=selected_exam,
                        defaults={'score': score, 'remarks': remarks}
                    )
            messages.success(request, f"Grades for {selected_exam.name} have been saved.")
            return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                           class_id=class_id, subject_id=subject_id, exam_id=exam.id)

    # Get all students in the class
    students = Student.objects.filter(class_group=class_group).order_by('user__last_name', 'user__first_name')
    # Get all exams associated with this class/subject through existing grades
    exam_ids = Grade.objects.filter(student__in=students, subject=subject).values_list('exam_id', flat=True).distinct()
    exams = Exam.objects.filter(id__in=exam_ids).order_by('-date')
    terms = Term.objects.all().order_by('-academic_year__year', 'name')
    
    # Create forms for each student
    forms = []
    # Get grades for selected exam
    student_grades = {}
    if selected_exam:
        grades = Grade.objects.filter(student__in=students, subject=subject, exam=selected_exam)
        for grade in grades:
            student_grades[grade.student_id] = grade

    for student in students:
        grade = student_grades.get(student.id)
        form = GradeInputForm(instance=grade, student=student)
        forms.append((student, form))

    context = {
        'teacher': teacher,
        'class_group': class_group,
        'subject': subject,
        'exams': exams,
        'terms': terms,
        'selected_exam': selected_exam,
        'forms': forms,
        'students': students,  # Add students list to context
        'student_grades': student_grades  # Add grades mapping to context
    }
    return render(request, 'dashboards/input_grades.html', context)
    return render(request, 'dashboards/input_grades.html', context)

# Admin Students View
@login_required(login_url='login')
def admin_students(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Student, User
    students = Student.objects.select_related('user', 'class_group').all()
    search_query = request.GET.get('search', '').strip()
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(admission_no__icontains=search_query)
        )
    add_student_form = AddStudentForm()
    if request.method == 'POST' and 'add_student' in request.POST:
        add_student_form = AddStudentForm(request.POST)
        if add_student_form.is_valid():
            from django.db import IntegrityError
            try:
                # Create user first
                user = User.objects.create_user(
                    username=add_student_form.cleaned_data['username'],
                    email=add_student_form.cleaned_data['email'],
                    first_name=add_student_form.cleaned_data['first_name'],
                    last_name=add_student_form.cleaned_data['last_name'],
                    role='student',
                    password=add_student_form.cleaned_data['password']
                )
                student = add_student_form.save(commit=False)
                student.user = user
                student.save()
                add_student_form = AddStudentForm()  # Reset form
                from django.contrib import messages
                messages.success(request, 'Student added successfully!')
                return redirect('admin_students')
            except IntegrityError as e:
                from django.contrib import messages
                if 'username' in str(e):
                    messages.error(request, 'A user with that username already exists. Please choose a different username.')
                elif 'email' in str(e):
                    messages.error(request, 'A user with that email already exists. Please choose a different email.')
                else:
                    messages.error(request, 'An error occurred while adding the student. Please check the data and try again.')
    context = {
        'students': students,
        'add_student_form': add_student_form,
    }
    return render(request, 'dashboards/admin_students.html', context)

# Admin Classes View
@login_required(login_url='login')
def admin_classes(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Class, Student, Subject, Teacher, TeacherClassAssignment, Grade
    from django.contrib import messages
    from .forms import AddClassForm
    add_class_form = AddClassForm()
    # Handle assignment POST and AddClassForm
    if request.method == 'POST':
        if 'assign_teacher' in request.POST:
            class_id = request.POST.get('class_id')
            subject_id = request.POST.get('subject_id')
            teacher_id = request.POST.get('teacher_id')
            if class_id and subject_id and teacher_id:
                try:
                    class_obj = Class.objects.get(id=class_id)
                    subject_obj = Subject.objects.get(id=subject_id)
                    teacher_obj = Teacher.objects.get(id=teacher_id)
                    # Update or create assignment
                    assignment, created = TeacherClassAssignment.objects.update_or_create(
                        class_group=class_obj, subject=subject_obj,
                        defaults={'teacher': teacher_obj}
                    )
                    messages.success(request, f"Assigned {teacher_obj.user.get_full_name()} to {subject_obj.name} for {class_obj.name}.")
                except (Class.DoesNotExist, Subject.DoesNotExist, Teacher.DoesNotExist):
                    messages.error(request, "Invalid class, subject, or teacher selection.")
            else:
                messages.error(request, "Please select class, subject, and teacher.")
        elif 'assign_class_teacher' in request.POST:
            class_id = request.POST.get('class_id')
            teacher_id = request.POST.get('teacher_id')
            if class_id and teacher_id:
                try:
                    class_obj = Class.objects.get(id=class_id)
                    teacher_obj = Teacher.objects.get(id=teacher_id)
                    class_obj.class_teacher = teacher_obj
                    class_obj.save()
                    messages.success(request, f"Changed class teacher for {class_obj.name} to {teacher_obj.user.get_full_name()}.")
                except (Class.DoesNotExist, Teacher.DoesNotExist):
                    messages.error(request, "Invalid class or teacher selection.")
            else:
                messages.error(request, "Please select both class and teacher.")
        elif 'add_class' in request.POST:
            add_class_form = AddClassForm(request.POST)
            if add_class_form.is_valid():
                add_class_form.save()
                messages.success(request, "Class added successfully.")
                add_class_form = AddClassForm()  # reset form
            else:
                messages.error(request, "Please correct the errors below.")
    # Prepare data for GET
    classes = Class.objects.all()
    all_subjects = Subject.objects.all()
    all_teachers = Teacher.objects.select_related('user').all()
    class_list = [];
    for c in classes:
        # For this class, get all subjects (could be all, or you may want to filter)
        # Build a mapping of teachers to their assigned subjects for this class
        assignments = TeacherClassAssignment.objects.filter(class_group=c).select_related('teacher__user', 'subject')
        teacher_subject_map = {}
        for assign in assignments:
            teacher = assign.teacher
            if teacher not in teacher_subject_map:
                teacher_subject_map[teacher] = []
            teacher_subject_map[teacher].append(assign.subject)
        teachers_and_subjects = []
        for teacher, subjects in teacher_subject_map.items():
            teachers_and_subjects.append({
                'teacher': teacher,
                'subjects': subjects
            })
        # For backward compatibility in template, assign to 'subjects_and_teachers'
        subjects_and_teachers = teachers_and_subjects

        class_students = Student.objects.filter(class_group=c, graduated=False).select_related('user')
        # Compute subject performance for this class
        from django.db.models import Avg
        subject_performance = []
        for subj in all_subjects:
            avg_score = Grade.objects.filter(student__class_group=c, subject=subj).aggregate(avg=Avg('score'))['avg']
            subject_performance.append({'subject': subj.name, 'avg_score': avg_score or 0})
        class_list.append({
            'id': c.id,
            'name': c.name,
            'level': c.level,
            'class_teacher': c.class_teacher.user.get_full_name() if c.class_teacher else None,
            'class_teacher_username': c.class_teacher.user.username if c.class_teacher else None,
            'subject_performance': subject_performance,
            'subjects_and_teachers': subjects_and_teachers,
        })
    # Optionally, provide all graduated students for display
    graduated_students = Student.objects.filter(graduated=True).select_related('user')
    # Calculate graduation year info
    import datetime
    current_year = datetime.date.today().year
    graduated_info = []
    for student in graduated_students:
        # Try to find the last academic year in which the student was active (based on their grades)
        last_grade = student.grade_set.select_related('exam__term__academic_year').order_by('-exam__term__academic_year__year').first()
        grad_year = None
        if last_grade and last_grade.exam and last_grade.exam.term and last_grade.exam.term.academic_year:
            # Extract the year as int (handles '2024' or '2024/2025')
            import re
            match = re.match(r'(\d{4})', str(last_grade.exam.term.academic_year.year))
            if match:
                grad_year = int(match.group(1))
        if grad_year:
            years_ago = current_year - grad_year
            if years_ago == 0:
                status = 'graduated this year'
            elif years_ago == 1:
                status = 'graduated last year'
            else:
                status = f'graduated {years_ago} years ago'
        else:
            status = 'graduation year unknown'
        graduated_info.append({'student': student, 'status': status})
    context = {
        'class_list': class_list,
        'graduated_students': graduated_students,
        'graduated_info': graduated_info,
        'add_class_form': add_class_form,
        'all_subjects': all_subjects,
        'all_teachers': all_teachers,
    }
    return render(request, 'dashboards/admin_classes.html', context)

@login_required(login_url='login')
def class_profile(request, class_id):
    from .models import Class, Student, TeacherClassAssignment, Subject
    class_obj = Class.objects.select_related('class_teacher').get(id=class_id)
    students = Student.objects.filter(class_group=class_obj).select_related('user')
    assignments = TeacherClassAssignment.objects.filter(class_group=class_obj).select_related('teacher__user', 'subject')
    subjects_and_teachers = []
    for subj in Subject.objects.all():
        assignment = assignments.filter(subject=subj).first()
        subjects_and_teachers.append({
            'subject': subj,
            'teacher': assignment.teacher if assignment else None,
        })
    context = {
        'class_obj': class_obj,
        'students': students,
        'subjects_and_teachers': subjects_and_teachers,
    }
    return render(request, 'dashboards/class_profile.html', context)

@login_required(login_url='login')
def edit_class(request, class_id):
    from .models import Class, Teacher
    from django.contrib import messages
    class_obj = Class.objects.get(id=class_id)
    if request.method == 'POST':
        level = request.POST.get('level')
        stream = request.POST.get('stream')
        class_teacher_id = request.POST.get('class_teacher')
        if level and stream:
            class_obj.name = f"Grade {level} {stream}"
            class_obj.level = level
            if class_teacher_id:
                try:
                    class_obj.class_teacher = Teacher.objects.get(id=class_teacher_id)
                except Teacher.DoesNotExist:
                    class_obj.class_teacher = None
            else:
                class_obj.class_teacher = None
            class_obj.save()
            messages.success(request, 'Class updated successfully!')
            return redirect('admin_classes')
    context = {'class_obj': class_obj}
    return render(request, 'dashboards/edit_class.html', context)

@login_required(login_url='login')
def delete_class(request, class_id):
    from .models import Class, Student, TeacherClassAssignment
    from django.contrib import messages
    class_obj = Class.objects.get(id=class_id)
    if Student.objects.filter(class_group=class_obj).exists() or TeacherClassAssignment.objects.filter(class_group=class_obj).exists():
        messages.error(request, 'Cannot delete class: class has students or teacher assignments.')
        return redirect('admin_classes')
    if request.method == 'POST':
        class_obj.delete()
        messages.success(request, 'Class deleted successfully.')
        return redirect('admin_classes')
    context = {'class_obj': class_obj}
    return render(request, 'dashboards/delete_class.html', context)



# Admin Academic Years & Terms View
from .models import AcademicYear, Term
from django.views.decorators.csrf import csrf_protect

@login_required(login_url='login')
def admin_academic_years(request):
    if request.user.role != 'admin':
        return redirect('dashboard')

    edit_term_id = None
    edit_term_form = None

    if request.method == 'POST':
        if 'show_edit_term' in request.POST:
            edit_term_id = request.POST.get('term_id')
            if edit_term_id:
                try:
                    term = Term.objects.get(id=edit_term_id)
                    edit_term_form = EditTermDatesForm(instance=term)
                except Term.DoesNotExist:
                    messages.error(request, "Term not found.")
        elif 'add_year' in request.POST:
            year = request.POST.get('year')
            if year:
                # Check if the year already exists (case insensitive)
                if AcademicYear.objects.filter(year__iexact=year).exists():
                    messages.error(request, f"Academic Year '{year}' already exists. If you want to add terms, use the form below.")
                    return redirect('admin_academic_years')
                academic_year_obj = AcademicYear.objects.create(year=year)
                # Auto-create terms if none exist for this year
                import re
                year_match = re.match(r'(\d{4})', year)
                if year_match:
                    base_year = int(year_match.group(1))
                    # Define terms and holidays
                    import datetime
                    terms = [
                        ('Term 1', datetime.date(base_year, 1, 1), datetime.date(base_year, 3, 31)),
                        ('Term 2', datetime.date(base_year, 5, 1), datetime.date(base_year, 7, 31)),
                        ('Term 3', datetime.date(base_year, 9, 1), datetime.date(base_year, 11, 30)),
                    ]
                    for name, start, end in terms:
                        Term.objects.create(name=name, academic_year=academic_year_obj, start_date=start, end_date=end)
                messages.success(request, f'Academic Year {year} added.')
                return redirect('admin_academic_years')
        elif 'add_term' in request.POST:
            year_id = request.POST.get('year_id')
            term_name = request.POST.get('term_name')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            if year_id and term_name and start_date and end_date:
                academic_year = AcademicYear.objects.get(id=year_id)
                Term.objects.get_or_create(
                    name=term_name,
                    academic_year=academic_year,
                    defaults={
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )
                messages.success(request, f'Term {term_name} added to {academic_year.year}.')
                return redirect('admin_academic_years')
        elif 'edit_term_dates' in request.POST:
            edit_term_id = request.POST.get('term_id')
            term = Term.objects.get(id=edit_term_id)
            edit_term_form = EditTermDatesForm(request.POST, instance=term)
            if edit_term_form.is_valid():
                edit_term_form.save()
                messages.success(request, f"Updated dates for {term.name}.")
                return redirect('admin_academic_years')
            else:
                messages.error(request, "Failed to update term dates. Please check the form.")
        elif 'run_promotion' in request.POST:
            # Trigger the promote_students management command
            import subprocess
            import sys
            result = subprocess.run([sys.executable, 'manage.py', 'promote_students'], capture_output=True, text=True)
            if result.returncode == 0:
                messages.success(request, 'Promotion and graduation process completed successfully.')
            else:
                messages.error(request, 'Promotion failed: ' + result.stderr)
            return redirect('admin_academic_years')

    import datetime
    today = datetime.date.today()
    # Only show years with at least one term whose end_date is today or in the future
    all_years = AcademicYear.objects.prefetch_related('terms').all().order_by('-year')
    academic_years = []
    for year in all_years:
        terms = year.terms.all()
        if any(term.end_date and term.end_date >= today for term in terms):
            academic_years.append(year)

    # Find the current term based on today's date
    current_term = None
    current_year = None
    graduation_ready = False
    graduation_year = None
    for year in academic_years:
        terms = sorted(year.terms.all(), key=lambda t: t.start_date or datetime.date.min)
        for idx, term in enumerate(terms):
            if term.start_date and term.end_date:
                if term.start_date <= today <= term.end_date:
                    current_term = term
                    current_year = year
                    break
        # Graduation: after last term's end date
        if terms and all(t.end_date for t in terms):
            last_term = terms[-1]
            if last_term.end_date < today:
                graduation_ready = True
                graduation_year = year
    context = {
        'academic_years': academic_years,
        'current_term': current_term,
        'current_year': current_year,
        'graduation_ready': graduation_ready,
        'graduation_year': graduation_year,
        'edit_term_id': edit_term_id,
        'edit_term_form': edit_term_form,
    }
    return render(request, 'dashboards/admin_academic_years.html', context)

# Admin Analytics View
import json
from .forms import AddSubjectForm
from django.db.models import Avg

@login_required(login_url='login')
def admin_analytics(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Subject, Grade
    subjects = Subject.objects.all()
    avg_performance = []
    for subject in subjects:
        avg_score = Grade.objects.filter(subject=subject).aggregate(avg=Avg('score'))['avg']
        avg_performance.append({'subject': subject.name, 'avg_score': avg_score or 0})
    subject_labels = json.dumps([item['subject'] for item in avg_performance])
    avg_scores = json.dumps([item['avg_score'] for item in avg_performance])
    context = {
        'avg_performance': avg_performance,
        'subject_labels': subject_labels,
        'avg_scores': avg_scores,
    }
    return render(request, 'dashboards/admin_analytics.html', context)

@login_required(login_url='login')
def admin_subjects(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Subject, Teacher, Department
    subjects = Subject.objects.all()
    # Build a department list from subjects (placeholder, since Subject has no department FK)
    departments = set()
    for subject in subjects:
        # If you later add a department field to Subject, update here
        dept = getattr(subject, 'department', None)
        if dept:
            departments.add(dept)
        # Attach teachers to each subject (assuming a many-to-many or related name)
        if hasattr(subject, 'teachers'):
            subject.teachers = subject.teachers.all()
        elif hasattr(subject, 'teacher_set'):
            subject.teachers = subject.teacher_set.all()
        else:
            subject.teachers = []
    add_subject_form = AddSubjectForm()
    if request.method == 'POST' and 'add_subject' in request.POST:
        add_subject_form = AddSubjectForm(request.POST)
        if add_subject_form.is_valid():
            add_subject_form.save()
            messages.success(request, 'Subject added successfully!')
            add_subject_form = AddSubjectForm()
        else:
            messages.error(request, 'Please correct the errors below.')
    context = {
        'subjects': subjects,
        'departments': list(departments),
        'add_subject_form': add_subject_form,
    }
    return render(request, 'dashboards/admin_subjects.html', context)

def custom_logout_view(request):
    # Clear all messages
    list(messages.get_messages(request))
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('login')

@login_required(login_url='login')
def teacher_exams(request, teacher_id):
    from .models import TeacherClassAssignment, Student, Subject, Teacher
    teacher = Teacher.objects.get(id=teacher_id)
    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('subject', 'class_group')
    subject_students = {}
    for assignment in assignments:
        students = Student.objects.filter(class_group=assignment.class_group)
        subject_students[(assignment.subject, assignment.class_group)] = students
    context = {
        'teacher': teacher,
        'subject_students': subject_students,
    }
    return render(request, 'dashboards/teacher_exams.html', context)

@login_required(login_url='login')
def teacher_exam_entry(request, teacher_id, class_id, subject_id, exam_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.user != teacher.user:
        return redirect('dashboard')

    if request.method == 'POST':
        scores = request.POST.getlist('scores[]')
        student_ids = request.POST.getlist('student_ids[]')
        
        exam = get_object_or_404(Exam, id=exam_id)
        subject = get_object_or_404(Subject, id=subject_id)
        class_group = get_object_or_404(Class, id=class_id)
        
        # Validate scores
        for score in scores:
            try:
                score = float(score)
                if score < 0 or score > 100:
                    messages.error(request, 'Scores must be between 0 and 100')
                    return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                                  class_id=class_id, subject_id=subject_id, exam_id=exam_id)
            except ValueError:
                messages.error(request, 'Invalid score format')
                return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                              class_id=class_id, subject_id=subject_id, exam_id=exam_id)

        # Save scores
        try:
            for student_id, score in zip(student_ids, scores):
                student = Student.objects.get(id=student_id)
                Grade.objects.update_or_create(
                    student=student,
                    exam=exam,
                    subject=subject,
                    defaults={'score': score}
                )
            messages.success(request, 'Scores saved successfully')
        except Exception as e:
            messages.error(request, f'Error saving scores: {str(e)}')
            return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                          class_id=class_id, subject_id=subject_id, exam_id=exam_id)

        return redirect('teacher_exam_entry', teacher_id=teacher_id, 
                       class_id=class_id, subject_id=subject_id, exam_id=exam_id)

    # Get teacher's subjects and classes
    subjects = teacher.subjects.all()
    classes = Class.objects.filter(teachers=teacher)
    
    # Get exam details
    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)
    class_group = get_object_or_404(Class, id=class_id)

    # Get students for this class and subject
    students = Student.objects.filter(
        class_group_id=class_id
    ).order_by('user__last_name', 'user__first_name')

    # Get existing grades for this exam
    grade_map = {}
    existing_grades = Grade.objects.filter(
        exam=exam,
        subject=subject,
        student__in=students
    )
    for grade in existing_grades:
        grade_map[grade.student_id] = grade.score

    context = {
        'teacher': teacher,
        'subjects': subjects,
        'classes': classes,
        'exam': exam,
        'subject': subject,
        'class_group': class_group,
        'students': students,
        'grade_map': grade_map,
    }
    return render(request, 'dashboards/teacher_exam_entry.html', context)

@login_required(login_url='login')
def upload_marksheet(request):
    if request.method == 'POST':
        file = request.FILES['file']
        import pandas as pd
        import datetime

        df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]

        # Flexible required columns check
        required_cols_student = ['admission_no', 'student_name']
        required_cols_subject = ['subject_code', 'subject_name']
        other_required_cols = ['exam_name', 'term', 'academic_year', 'score']

        has_student_id = any(col in df.columns for col in required_cols_student)
        has_subject_id = any(col in df.columns for col in required_cols_subject)
        has_others = all(col in df.columns for col in other_required_cols)

        if not (has_student_id and has_subject_id and has_others):
            msg = "File is missing required columns. It must contain ('admission_no' or 'student_name'), ('subject_code' or 'subject_name'), 'exam_name', 'term', 'academic_year', and 'score'."
            messages.error(request, msg)
            return redirect('upload_marksheet')

        errors = []
        try:
            for index, row in df.iterrows():
                try:
                    # Find Student
                    student = None
                    if 'admission_no' in df.columns and pd.notna(row.get('admission_no')):
                        student = Student.objects.get(admission_no=row['admission_no'])
                    elif 'student_name' in df.columns and pd.notna(row.get('student_name')):
                        full_name = str(row['student_name']).strip()
                        parts = full_name.split(' ', 1)
                        first_name = parts[0]
                        last_name = parts[1] if len(parts) > 1 else ''
                        
                        user_qs = User.objects.filter(
                            Q(username__iexact=full_name) |
                            (Q(first_name__iexact=first_name) & Q(last_name__iexact=last_name))
                        )
                        
                        if user_qs.count() == 1:
                            student = Student.objects.get(user=user_qs.first())
                        elif user_qs.count() > 1:
                            errors.append(f"Row {index+2}: Multiple students found for name '{full_name}'. Use admission number.")
                            continue
                        else:
                            errors.append(f"Row {index+2}: Student with name '{full_name}' not found.")
                            continue
                    else:
                        errors.append(f"Row {index+2}: Missing student identifier.")
                        continue

                    # Find Subject
                    subject = None
                    if 'subject_code' in df.columns and pd.notna(row.get('subject_code')):
                        subject = Subject.objects.get(code__iexact=str(row['subject_code']).strip())
                    elif 'subject_name' in df.columns and pd.notna(row.get('subject_name')):
                        subject_identifier = str(row['subject_name']).strip()
                        subject_qs = Subject.objects.filter(
                            Q(name__iexact=subject_identifier) | Q(code__iexact=subject_identifier)
                        )
                        if subject_qs.count() == 1:
                            subject = subject_qs.first()
                        else:
                            errors.append(f"Row {index+2}: Subject '{subject_identifier}' not found or is ambiguous.")
                            continue
                    else:
                        errors.append(f"Row {index+2}: Missing subject identifier.")
                        continue
                    
                    # Get or create other objects
                    academic_year, _ = AcademicYear.objects.get_or_create(year=row['academic_year'])
                    term, _ = Term.objects.get_or_create(name=row['term'], academic_year=academic_year)
                    exam, _ = Exam.objects.get_or_create(name=row['exam_name'], term=term, defaults={'date': datetime.date.today()})

                    # Update or create grade
                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        exam=exam,
                        defaults={'score': row['score']}
                    )
                except Exception as e:
                    errors.append(f'Row {index+2}: An unexpected error occurred: {e}')

            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, 'Marksheet uploaded successfully.')

        except Exception as e:
            messages.error(request, f'Error processing file: {e}')

        return redirect('upload_marksheet')

    teacher = request.user.teacher
    return render(request, 'dashboards/upload_marksheet.html', {'teacher': teacher})

def custom_login_view(request):
    # Always log out any existing user/session on visiting login page
    from django.contrib.auth import logout
    if request.user.is_authenticated:
        logout(request)
        # Optionally, add a message
        # messages.info(request, 'You have been logged out.')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        role = request.POST['role']

        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == role:
            login(request, user)
            if role == 'admin':
                return redirect('admin_overview')
            elif role == 'teacher':
                # Get teacher id and redirect properly
                if hasattr(user, 'teacher'):
                    return redirect('teacher_dashboard', teacher_id=user.teacher.id)
                else:
                    messages.error(request, 'No teacher profile found for this account.')
                    return redirect('login')
            elif role == 'student':
                return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials or role mismatch.')

    return render(request, 'auth/login.html')

# Admin Exams View
from django.contrib.auth.decorators import login_required
@login_required(login_url='login')
def admin_exams(request):
    from .forms import ExamForm
    from .models import Exam, Subject, Student, Grade, Class
    from django.contrib import messages
    import pandas as pd
    from django.db import transaction

    exam_form = ExamForm(request.POST or None)
    exams = Exam.objects.select_related('term').order_by('-date')
    latest_exam = exams.first() if exams.exists() else None
    table_html = None
    summary = {'added': 0, 'removed': 0, 'errors': []}

    # Handle exam creation POST
    if request.method == 'POST' and 'add_exam' in request.POST:
        if exam_form.is_valid():
            exam_form.save()
            messages.success(request, 'Exam created successfully!')
            exam_form = ExamForm()  # Reset form
        else:
            messages.error(request, 'Please correct the errors below.')

    # Helper: Build student-subject matrix for the latest exam
    def build_students_subjects_table():
        all_subjects = list(Subject.objects.all().order_by('name'))
        all_classes = list(Class.objects.all().order_by('name'))
        students_subjects_table = []
        for class_obj in all_classes:
            students = Student.objects.filter(class_group=class_obj).order_by('admission_no')
            for student in students:
                student_subjects = set(Grade.objects.filter(student=student).values_list('subject_id', flat=True))
                row = {
                    'admission_no': student.admission_no,
                    'name': student.full_name,
                    'class': class_obj.name,
                    'subjects': [subj.id in student_subjects for subj in all_subjects],
                    'subject_ids': list(student_subjects),
                }
                students_subjects_table.append(row)
        return students_subjects_table, all_subjects

    # Handle grade entry matrix POST
    if request.method == 'POST' and request.POST.get('submit_matrix'):
        updated = 0
        for key, value in request.POST.items():
            if key.startswith('marks-'):
                try:
                    _, admission_no, subject_id = key.split('-', 2)
                    score = value.strip()
                    if score == '':
                        continue
                    score = float(score)
                    student = Student.objects.get(admission_no=admission_no)
                    subject = Subject.objects.get(id=subject_id)
                    exam = latest_exam
                    if not exam:
                        continue
                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        exam=exam,
                        defaults={'score': score}
                    )
                    updated += 1
                except Exception:
                    continue
        messages.success(request, f"Successfully updated {updated} marks from matrix form.")

    # Handle bulk marksheet upload
    if request.method == 'POST' and request.FILES.get('marksheet'):
        excel_file = request.FILES['marksheet']
        is_preview = 'preview' in request.POST
        is_process = 'process' in request.POST
        try:
            df = pd.read_excel(excel_file)
            table_html = df.to_html(classes='table table-bordered table-striped', index=False)
            required_cols = ['admission_no', 'first_name', 'last_name', 'gender', 'birthdate', 'class_group']
            for col in required_cols:
                if col not in df.columns:
                    summary['errors'].append(f"Missing required column: {col}")
            if summary['errors']:
                messages.error(request, ' '.join(summary['errors']))
                students_subjects_table, all_subjects = build_students_subjects_table()
                return render(request, 'dashboards/admin_exams.html', {
                    'table_html': table_html,
                    'students_subjects_table': students_subjects_table,
                    'all_subjects': all_subjects,
                    'exam_form': exam_form,
                    'exams': exams,
                })
            # Clean and check for duplicates/missing
            seen = set()
            valid_rows = []
            for idx, row in df.iterrows():
                row_errors = []
                admission_no = str(row.get('admission_no', '')).strip()
                first_name = str(row.get('first_name', '')).strip()
                last_name = str(row.get('last_name', '')).strip()
                gender = str(row.get('gender', '')).strip()
                birthdate = row.get('birthdate')
                class_name = str(row.get('class_group', '')).strip()
                if not all([admission_no, first_name, last_name, gender, birthdate, class_name]):
                    row_errors.append(f"Row {idx+2}: Missing required data.")
                if admission_no in seen:
                    row_errors.append(f"Row {idx+2}: Duplicate admission_no {admission_no}.")
                seen.add(admission_no)
                if row_errors:
                    summary['errors'].extend(row_errors)
                else:
                    valid_rows.append({
                        'admission_no': admission_no,
                        'first_name': first_name,
                        'last_name': last_name,
                        'gender': gender,
                        'birthdate': birthdate,
                        'class_group': class_name
                    })
            if not valid_rows:
                messages.error(request, 'No valid students to import.')
                students_subjects_table, all_subjects = build_students_subjects_table()
                return render(request, 'dashboards/admin_exams.html', {
                    'table_html': table_html,
                    'students_subjects_table': students_subjects_table,
                    'all_subjects': all_subjects,
                    'exam_form': exam_form,
                    'exams': exams,
                })
            if is_preview:
                if summary['errors']:
                    messages.error(request, ' '.join(summary['errors']))
                else:
                    messages.info(request, 'Preview successful. No data has been added yet.')
                students_subjects_table, all_subjects = build_students_subjects_table()
                return render(request, 'dashboards/admin_exams.html', {
                    'table_html': table_html,
                    'students_subjects_table': students_subjects_table,
                    'all_subjects': all_subjects,
                    'exam_form': exam_form,
                    'exams': exams,
                })
            if is_process:
                from .models import Exam, Term, AcademicYear, User
                import datetime
                class_name = valid_rows[0]['class_group']
                class_group, _ = Class.objects.get_or_create(name=class_name)
                uploaded_adm_nos = set([row['admission_no'] for row in valid_rows])
                grades_processed = 0
                with transaction.atomic():
                    to_remove = Student.objects.filter(class_group=class_group).exclude(admission_no__in=uploaded_adm_nos)
                    for st in to_remove:
                        if st.user:
                            st.user.delete()
                        st.delete()
                        summary['removed'] += 1
                    for row in valid_rows:
                        if not Student.objects.filter(admission_no=row['admission_no']).exists():
                            user = User.objects.create_user(
                                username=row['admission_no'],
                                first_name=row['first_name'],
                                last_name=row['last_name'],
                                role='student'
                            )
                            user.set_password('student1234')
                            user.save()
                            Student.objects.create(
                                user=user,
                                admission_no=row['admission_no'],
                                class_group=class_group,
                                gender=row['gender'],
                                birthdate=row['birthdate']
                            )
                            summary['added'] += 1
                    year = str(datetime.date.today().year)
                    academic_year, _ = AcademicYear.objects.get_or_create(year=year)
                    term, _ = Term.objects.get_or_create(name='Term 1', academic_year=academic_year)
                    exam_name = f'Opener exams for {class_group.name}'
                    exam, _ = Exam.objects.get_or_create(name=exam_name, term=term, defaults={'date': datetime.date.today()})
                    subj_code_map = {s.code: s for s in Subject.objects.all()}
                    subject_cols = [col for col in df.columns if col not in ['admission_no', 'first_name', 'last_name', 'gender', 'birthdate', 'class_group']]
                    for idx, row in df.iterrows():
                        try:
                            student = Student.objects.get(admission_no=str(row['admission_no']).strip())
                        except Student.DoesNotExist:
                            continue
                        for subj_col in subject_cols:
                            score = row.get(subj_col, None)
                            if pd.isna(score):
                                continue
                            try:
                                score = float(score)
                            except (TypeError, ValueError):
                                continue
                            subj_code = subj_col
                            subject = subj_code_map.get(subj_code)
                            if not subject:
                                subject = Subject.objects.filter(name__iexact=subj_code).first()
                            if not subject:
                                continue
                            Grade.objects.update_or_create(
                                student=student,
                                subject=subject,
                                exam=exam,
                                defaults={'score': score}
                            )
                            grades_processed += 1
                messages.success(request, f"Added: {summary['added']}, Removed: {summary['removed']}, Grades processed: {grades_processed}. Errors: {'; '.join(summary['errors']) if summary['errors'] else 'None'}.")
        except Exception as e:
            messages.error(request, f'Error reading Excel file: {e}')
    students_subjects_table, all_subjects = build_students_subjects_table()
    context = {
        'exam_form': exam_form,
        'exams': exams,
        'table_html': table_html,
        'students_subjects_table': students_subjects_table,
        'all_subjects': all_subjects,
    }
    return render(request, 'dashboards/admin_exams.html', context)