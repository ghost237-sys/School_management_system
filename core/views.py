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
        return redirect('teacher_dashboard')
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
@login_required(login_url='login')
def admin_teachers(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Teacher
    teachers = Teacher.objects.select_related('user').all()
    context = {
        'teachers': teachers,
    }
    return render(request, 'dashboards/admin_teachers.html', context)

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