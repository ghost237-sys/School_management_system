from django.shortcuts import render, redirect
from django.contrib.auth import login , authenticate
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        role = request.POST.get('role')

        if form.is_valid():
            user = form.save(commit=False)
            user.role = role
            user.save()
            # If registering as teacher, create Teacher object
            if role == 'teacher':
                from .models import Teacher
                Teacher.objects.get_or_create(user=user)
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})



@login_required(login_url='login')
def dashboard(request):
    # Redirect admin to overview, others to their dashboards
    if request.user.role == 'admin':
        from django.urls import reverse
        return redirect(reverse('admin_overview'))
    elif request.user.role == 'teacher':
        return redirect('teacher_dashboard', teacher_id=request.user.teacher.id)
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    else:
        from django.contrib import messages
        messages.error(request, 'Unknown user role. Please contact admin.')
        return redirect('login')

# Admin Overview View
@login_required(login_url='login')
def admin_overview(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Student, Grade, Subject, Class
    from django.db.models import Avg
    # Total students
    total_students = Student.objects.count()
    # Average performance per subject
    subjects = Subject.objects.all()
    avg_performance = []
    for subject in subjects:
        avg_score = Grade.objects.filter(subject=subject).aggregate(avg=Avg('score'))['avg']
        avg_performance.append({'subject': subject.name, 'avg_score': avg_score or 0})
    # Top/Bottom performers
    classes = Class.objects.all()
    top_performers = []
    for class_group in classes:
        students = Student.objects.filter(class_group=class_group)
        for student in students:
            avg_score = Grade.objects.filter(student=student).aggregate(avg=Avg('score'))['avg']
            if avg_score is not None:
                top_performers.append({'student': student.user.username, 'class': class_group.name, 'avg_score': avg_score})
    top_performers_sorted = sorted(top_performers, key=lambda x: x['avg_score'], reverse=True)[:5]
    bottom_performers_sorted = sorted(top_performers, key=lambda x: x['avg_score'])[:5]
    # Split avg_performance into two halves
    mid = (len(avg_performance) + 1) // 2
    avg_performance_1 = avg_performance[:mid]
    avg_performance_2 = avg_performance[mid:]
    context = {
        'total_students': total_students,
        'avg_performance_1': avg_performance_1,
        'avg_performance_2': avg_performance_2,
        'top_performers': top_performers_sorted,
        'bottom_performers': bottom_performers_sorted,
    }
    return render(request, 'dashboards/admin_overview.html', context)

# Admin Teachers View
from .forms import AddTeacherForm
from django.shortcuts import get_object_or_404

@login_required(login_url='login')
def admin_teachers(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Teacher, Department, Subject, User
    from django.db.models import Q
    teachers = Teacher.objects.select_related('user', 'department').prefetch_related('subjects', 'teacherclassassignment_set__class_group').all()
    departments = Department.objects.all()
    subjects = Subject.objects.all()
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
            if form.cleaned_data['password']:
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
    from .models import Teacher, User
    teacher = get_object_or_404(Teacher, id=teacher_id)
    user = teacher.user
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'Teacher deleted successfully.')
        return redirect('admin_teachers')
    return render(request, 'dashboards/delete_teacher.html', {'teacher': teacher})


# Teacher Dashboard View
@login_required(login_url='login')
def teacher_dashboard(request, teacher_id):
    from .models import Teacher, TeacherClassAssignment, Subject, Grade, Class
    from django.db.models import Avg, Max
    teacher = Teacher.objects.select_related('user').prefetch_related('subjects').get(id=teacher_id)
    # Assignments: classes and subjects
    assignments = []
    conflicts = []
    class_assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group').prefetch_related('subjects')
    for assign in class_assignments:
        assignments.append({
            'class_group': assign.class_group,
            'subjects': assign.subjects.all()
        })
    # Simple conflict check: same subject assigned to multiple teachers in same class
    for assign in class_assignments:
        for subject in assign.subjects.all():
            others = TeacherClassAssignment.objects.filter(class_group=assign.class_group, subjects=subject).exclude(teacher=teacher)
            if others.exists():
                for other in others:
                    conflicts.append(f"Subject {subject.name} for {assign.class_group.name} also assigned to {other.teacher.user.get_full_name()}")
    # Performance: avg score, last marked, trend
    performance = []
    for subject in teacher.subjects.all():
        # Get grades for this subject in classes the teacher is assigned to
        class_ids = [a['class_group'].id for a in assignments]
        grades = Grade.objects.filter(subject=subject, student__class_group_id__in=class_ids)
        avg_score = grades.aggregate(avg=Avg('score'))['avg']
        last_marked = None
        if grades.exists() and hasattr(grades.first(), 'exam'):
            last_marked = grades.order_by('-exam__id').first().exam.date if hasattr(grades.first().exam, 'date') else None
        # Dummy trend logic: could be improved with more data
        trend = 'up' if avg_score and avg_score > 75 else 'down' if avg_score and avg_score < 50 else 'neutral'
        performance.append({
            'subject': subject,
            'avg_score': avg_score or 0,
            'last_marked': last_marked,
            'trend': trend,
        })
    # Timetable: dummy structure (should be replaced with real timetable logic)
    timetable = {
        'Monday':    [None, None, None, None, None],
        'Tuesday':   [None, None, None, None, None],
        'Wednesday': [None, None, None, None, None],
        'Thursday':  [None, None, None, None, None],
        'Friday':    [None, None, None, None, None],
    }
    # Example: fill in timetable slots from assignments (very basic)
    slot_names = ['8:00-9:00', '9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00']
    for i, assign in enumerate(assignments):
        for j, subject in enumerate(assign['subjects']):
            day = list(timetable.keys())[i % 5]
            timetable[day][j % 5] = f"{subject.name} ({assign['class_group'].name})"
    context = {
        'teacher': teacher,
        'teacher_id': teacher.id,
        'assignments': assignments,
        'performance': performance,
        'timetable': timetable,
        'class_count': class_assignments.count(),
        'conflicts': conflicts,
    }
    return render(request, 'dashboards/teacher_dashboard.html', context)

# Admin Students View
@login_required(login_url='login')
def admin_students(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Student
    students = Student.objects.select_related('user', 'class_group').all()
    context = {
        'students': students,
    }
    return render(request, 'dashboards/admin_students.html', context)

# Admin Classes View
@login_required(login_url='login')
def admin_classes(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Class, Student
    classes = Class.objects.all()
    class_list = []
    for c in classes:
        class_students = Student.objects.filter(class_group=c).select_related('user')
        class_list.append({
            'id': c.id,
            'name': c.name,
            'level': c.level,
            'class_teacher': c.class_teacher.user.get_full_name() if c.class_teacher else None,
            'class_teacher_username': c.class_teacher.user.username if c.class_teacher else None,
            'students': list(class_students),
        })
    context = {
        'class_list': class_list,
    }
    return render(request, 'dashboards/admin_classes.html', context)

# Admin Analytics View
@login_required(login_url='login')
def admin_analytics(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    return render(request, 'dashboards/admin_analytics.html')

# Admin Subjects View
@login_required(login_url='login')
def admin_subjects(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Grade, Subject
    from django.db.models import Avg
    subjects = Subject.objects.all()
    avg_performance = []
    for subject in subjects:
        avg_score = Grade.objects.filter(subject=subject).aggregate(avg=Avg('score'))['avg']
        avg_performance.append({'subject': subject.name, 'avg_score': avg_score or 0})
    context = {
        'avg_performance': avg_performance,
    }
    return render(request, 'dashboards/admin_subjects.html', context)

def custom_login_view(request):
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
                return redirect('teacher_dashboard')
            elif role == 'student':
                return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials or role mismatch.')

    return render(request, 'auth/login.html')