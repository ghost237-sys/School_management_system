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



@login_required(login_url='login')  # Explicit login redirection
def dashboard(request):
    print('User role:', request.user.role)  # Debug log
    if request.user.role == 'admin':
        from .models import Student, Grade, Subject, Class
        from django.db.models import Avg, Max, Min

        # Total students
        total_students = Student.objects.count()

        # Average performance per subject
        subjects = Subject.objects.all()
        avg_performance = []
        for subject in subjects:
            avg_score = Grade.objects.filter(subject=subject).aggregate(avg=Avg('score'))['avg']
            avg_performance.append({'subject': subject.name, 'avg_score': avg_score or 0})

        # Top/Bottom performers per class (by average score)
        classes = Class.objects.all()
        top_performers = []
        bottom_performers = []
        for class_group in classes:
            students = Student.objects.filter(class_group=class_group)
            for student in students:
                avg_score = Grade.objects.filter(student=student).aggregate(avg=Avg('score'))['avg']
                if avg_score is not None:
                    top_performers.append({'student': student.user.username, 'class': class_group.name, 'avg_score': avg_score})
        # Sort for top and bottom
        top_performers_sorted = sorted(top_performers, key=lambda x: x['avg_score'], reverse=True)[:5]
        bottom_performers_sorted = sorted(top_performers, key=lambda x: x['avg_score'])[:5]

        from .models import Teacher, User, TeacherClassAssignment
        # All teachers and students
        teachers = Teacher.objects.select_related('user').all()
        classes = Class.objects.all()
        # Prepare class list with teacher and students
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

        # Handle POST: assign teacher to class
        if request.method == 'POST' and 'assign_teacher' in request.POST:
            teacher_id = request.POST.get('teacher_id')
            class_id = request.POST.get('class_id')
            try:
                teacher = Teacher.objects.get(id=teacher_id)
                class_obj = Class.objects.get(id=class_id)
                class_obj.class_teacher = teacher
                class_obj.save()
                messages.success(request, f"Assigned {teacher.user.username} as class teacher for {class_obj.name}.")
            except Exception as e:
                messages.error(request, f"Assignment failed: {e}")

        context = {
            'total_students': total_students,
            'avg_performance': avg_performance,
            'top_performers': top_performers_sorted,
            'bottom_performers': bottom_performers_sorted,
            'teachers': teachers,
            'classes': classes,
            'class_list': class_list,
        }
        return render(request, 'dashboards/admin_dashboard.html', context)

    elif request.user.role == 'teacher':
        from .models import Teacher, TeacherClassAssignment, Class, Student, Subject, Grade
        from django.db.models import Avg, Count

        # Get teacher object
        teacher = Teacher.objects.get(user=request.user)
        # Classes taught by this teacher
        assignments = TeacherClassAssignment.objects.filter(teacher=teacher)
        classes = Class.objects.filter(id__in=assignments.values_list('class_group', flat=True).distinct())

        # For each class, get students and their grades for subjects taught
        class_data = []
        for class_group in classes:
            students = Student.objects.filter(class_group=class_group)
            subjects = assignments.filter(class_group=class_group).values_list('subject', flat=True)
            subjects = Subject.objects.filter(id__in=subjects)
            student_scores = []
            for student in students:
                grades = Grade.objects.filter(student=student, subject__in=subjects)
                avg_score = grades.aggregate(avg=Avg('score'))['avg']
                grade_dist = grades.values('grade_letter').annotate(count=Count('id'))
                student_scores.append({
                    'student': student.user.username,
                    'avg_score': avg_score or 0,
                    'grades': list(grades),
                    'grade_dist': list(grade_dist),
                })
            class_data.append({
                'class': class_group.name,
                'students': student_scores,
                'subjects': list(subjects),
            })

        context = {
            'class_data': class_data,
        }
        return render(request, 'dashboards/teacher_dashboard.html', context)

    elif request.user.role == 'student':
        return render(request, 'dashboards/student_dashboard.html')
    else:
        messages.error(request, 'Unknown user role. Please contact admin.')
        return redirect('login')




def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        role = request.POST['role']

        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == role:
            login(request, user)
            if role == 'admin':
                return redirect('admin_dashboard')
            elif role == 'teacher':
                return redirect('teacher_dashboard')
            elif role == 'student':
                return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials or role mismatch.')

    return render(request, 'auth/login.html')