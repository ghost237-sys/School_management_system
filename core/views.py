from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.utils.dateparse import parse_datetime
from django.db import transaction

import datetime
import openpyxl
import json
import pandas as pd

from .models import (
    User, Student, Teacher, Class, Subject, Exam, Term, Grade, 
    FeeCategory, FeeAssignment, FeePayment, Event, Deadline, 
    TeacherClassAssignment, Department, AcademicYear
)
from .forms import (
    AddStudentForm, StudentContactUpdateForm, EditStudentClassForm, FeeCategoryForm,
    FeeAssignmentForm, FeePaymentForm, GradeInputForm, ExamForm,
    EventForm, AddTeacherForm, AddSubjectForm, AddClassForm, EditTermDatesForm,
    GradeUploadForm, CustomUserCreationForm
)

@login_required(login_url='login')
def dashboard(request):
    user = request.user
    if user.role == 'admin':
        return redirect('admin_overview')
    elif user.role == 'teacher':
        teacher = get_object_or_404(Teacher, user=user)
        return redirect('teacher_dashboard', teacher_id=teacher.id)
    elif user.role == 'student':
        return redirect('student_profile')
    else:
        messages.error(request, "Invalid user role.")
        return redirect('login')


@login_required(login_url='login')
def student_profile(request):
    student = get_object_or_404(Student, user=request.user)
    context = {
        'student': student,
    }
    return render(request, 'dashboards/student_profile.html', context)

@login_required(login_url='login')
def upload_grades(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        form = GradeUploadForm(request.POST, request.FILES, teacher=teacher)
        if form.is_valid():
            exam = form.cleaned_data['exam']
            subject = form.cleaned_data['subject']
            class_group = form.cleaned_data['class_group']
            file = request.FILES['file']

            try:
                workbook = openpyxl.load_workbook(file)
                sheet = workbook.active

                # Create a mapping of student names to student objects for efficient lookup
                students_in_class = Student.objects.filter(class_group=class_group).select_related('user')
                student_map = {s.user.get_full_name().strip().lower(): s for s in students_in_class}

                # Check for duplicate names within the class, which would make lookups ambiguous
                from collections import Counter
                name_counts = Counter(student_map.keys())
                duplicates = [name for name, count in name_counts.items() if count > 1]
                if duplicates:
                    messages.error(request, f"Upload failed. The following student names are duplicated in the class: {', '.join(duplicates)}. Please resolve this issue before uploading.")
                    return redirect('upload_grades', teacher_id=teacher.id)

                for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not row or row[0] is None:
                        continue  # Skip empty rows

                    student_name, score = row[0], row[1]
                    student_name = str(student_name).strip().lower()

                    student = student_map.get(student_name)

                    if not student:
                        messages.error(request, f"Error on row {i}: Student '{row[0]}' not found in this class.")
                        continue

                    try:
                        score_float = float(score)
                        grade_letter, remarks = 'F', 'NEEDS IMPROVEMENT'
                        if 80 <= score_float <= 100:
                            grade_letter, remarks = 'A', 'EXCELLENT'
                        elif 60 <= score_float < 80:
                            grade_letter, remarks = 'B', 'VERY GOOD'
                        elif 40 <= score_float < 60:
                            grade_letter, remarks = 'C', 'GOOD'
                        elif 20 <= score_float < 40:
                            grade_letter, remarks = 'D', 'AVERAGE'

                        Grade.objects.update_or_create(
                            student=student,
                            exam=exam,
                            subject=subject,
                            defaults={'score': score_float, 'grade_letter': grade_letter, 'remarks': remarks}
                        )
                    except (ValueError, TypeError):
                        messages.error(request, f"Error on row {i}: Invalid score '{score}' for student '{row[0]}'. Please enter a number.")
                        continue

                messages.success(request, 'Grades have been uploaded and processed.')
                # Redirect to the results page for the uploaded grades
                return redirect('exam_results', teacher_id=teacher.id, class_id=class_group.id, subject_id=subject.id, exam_id=exam.id)

            except Exception as e:
                messages.error(request, f"Error reading the Excel file: {e}")

    else:
        form = GradeUploadForm(teacher=teacher)
    
    return render(request, 'dashboards/upload_grades.html', {'form': form, 'teacher': teacher})

@login_required(login_url='login')
def teacher_profile(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    # Only allow admin or the teacher themselves
    if not (request.user.role == 'admin' or request.user.id == teacher.user.id):
        return HttpResponseForbidden('You do not have permission to view this profile.')

    return render(request, 'dashboards/teacher_profile.html', {'teacher': teacher})

@login_required(login_url='login')
def teacher_dashboard(request, teacher_id):

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
        # Exam model does not have class_group, so filter with available fields
        # Count exams for the class's level and a specific term (e.g., the current or latest term)
        # For demo, we'll use the latest term (update as needed)
        from .models import Term
        latest_term = Term.objects.order_by('-id').first()
        if latest_term:
            total_exams = Exam.objects.filter(level=assign.class_group.level, term=latest_term).count()
        else:
            total_exams = Exam.objects.filter(level=assign.class_group.level).count()
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
    teacher = get_object_or_404(Teacher, id=teacher_id)

    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        subject_id = request.POST.get('subject_id')
        exam_id = request.POST.get('exam_id')

        if not all([class_id, subject_id, exam_id]):
            messages.error(request, 'Please select a class, subject, and exam.')
            return redirect('manage_grades', teacher_id=teacher.id)

        return redirect('input_grades', teacher_id=teacher.id, class_id=class_id, subject_id=subject_id, exam_id=exam_id)

    assignments = TeacherClassAssignment.objects.filter(teacher=teacher).select_related('class_group', 'subject')
    
    # Create a unique list of classes and subjects taught by the teacher
    teacher_classes = sorted(list(set(a.class_group for a in assignments if a.class_group)), key=lambda c: c.name)
    teacher_subjects = Subject.objects.filter(teacherclassassignment__teacher=teacher).distinct().order_by('name')
    
    exams = Exam.objects.all().order_by('-date')

    context = {
        'teacher': teacher,
        'teacher_classes': teacher_classes,
        'teacher_subjects': teacher_subjects,
        'exams': exams,
    }
    return render(request, 'dashboards/manage_grades.html', context)



@login_required(login_url='login')
def input_grades(request, teacher_id, class_id, subject_id, exam_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    class_group = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == 'POST':
        students = Student.objects.filter(class_group=class_group)
        for student in students:
            score_str = request.POST.get(f'score_{student.id}')
            if score_str and score_str.strip():
                try:
                    score = float(score_str)
                    grade_letter, remarks = 'F', 'NEEDS IMPROVEMENT'
                    if 80 <= score <= 100:
                        grade_letter, remarks = 'A', 'EXCELLENT'
                    elif 60 <= score < 80:
                        grade_letter, remarks = 'B', 'VERY GOOD'
                    elif 40 <= score < 60:
                        grade_letter, remarks = 'C', 'GOOD'
                    elif 20 <= score < 40:
                        grade_letter, remarks = 'D', 'AVERAGE'

                    Grade.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults={'score': score, 'grade_letter': grade_letter, 'remarks': remarks}
                    )
                except (ValueError, TypeError):
                    messages.error(request, f"Invalid score for student {student.id}. Please enter a number.")
                    continue
        
        messages.success(request, 'Grades saved successfully!')
        return redirect('exam_results', teacher_id=teacher.id, class_id=class_group.id, subject_id=subject.id, exam_id=exam.id)

    students = Student.objects.filter(class_group=class_group).order_by('user__last_name', 'user__first_name')
    grades = Grade.objects.filter(student__in=students, subject=subject, exam=exam).select_related('student')
    
    grades_map = {grade.student.id: grade for grade in grades}

    for student in students:
        student.grade = grades_map.get(student.id)

    context = {
        'teacher': teacher,
        'class_group': class_group,
        'subject': subject,
        'exam': exam,
        'students': students,
    }
    return render(request, 'dashboards/input_grades.html', context)


@login_required(login_url='login')
def exam_results(request, teacher_id, class_id, subject_id, exam_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    class_group = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    exam = get_object_or_404(Exam, id=exam_id)

    students = Student.objects.filter(class_group=class_group).order_by('user__last_name', 'user__first_name')
    grades = Grade.objects.filter(student__in=students, subject=subject, exam=exam).select_related('student')

    grades_map = {grade.student.id: grade for grade in grades}

    for student in students:
        student.grade = grades_map.get(student.id)

    context = {
        'teacher': teacher,
        'class_group': class_group,
        'subject': subject,
        'exam': exam,
        'students': students,
    }
    return render(request, 'dashboards/exam_results.html', context)


@login_required(login_url='login')
def gradebook(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)

    # Get all unique classes and subjects assigned to the teacher
    teacher_classes = Class.objects.filter(teacherclassassignment__teacher=teacher).distinct()
    teacher_subjects = Subject.objects.filter(teacher=teacher).distinct()

    selected_class = None
    selected_subject = None
    students_grades = []
    exams = []

    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        subject_id = request.POST.get('subject_id')

        if class_id and subject_id:
            selected_class = get_object_or_404(Class, id=class_id)
            selected_subject = get_object_or_404(Subject, id=subject_id)

            # Fetch students in the selected class
            students = Student.objects.filter(class_group=selected_class).order_by('user__last_name', 'user__first_name')
            
            # Fetch all exams that have grades for this subject and class
            grades_for_subject = Grade.objects.filter(subject=selected_subject, student__class_group=selected_class)
            exam_ids = grades_for_subject.values_list('exam_id', flat=True).distinct()
            exams = Exam.objects.filter(id__in=exam_ids).order_by('date')

            # Prepare a data structure for the template
            for student in students:
                grades = {grade.exam_id: grade for grade in grades_for_subject.filter(student=student)}
                students_grades.append({
                    'student': student,
                    'grades': [grades.get(exam.id) for exam in exams]
                })

    context = {
        'teacher': teacher,
        'teacher_classes': teacher_classes,
        'teacher_subjects': teacher_subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'students_grades': students_grades,
        'exams': exams,
    }
    return render(request, 'dashboards/gradebook.html', context)


# Admin Students View

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

@login_required(login_url='login')
@login_required(login_url='login')
def admin_overview(request):
    if not request.user.role == 'admin':
        return HttpResponseForbidden("You are not authorized to view this page.")
    
    # Placeholder context
    context = {
        'teacher_count': Teacher.objects.count(),
        'student_count': Student.objects.count(),
        'class_count': Class.objects.count(),
        'subject_count': Subject.objects.count(),
    }
    return render(request, 'dashboards/admin_overview.html', context)

def edit_user(request, user_id):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import User
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', user.role)
        is_active = 'is_active' in request.POST
        # Check for username/email uniqueness
        if User.objects.exclude(id=user.id).filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.exclude(id=user.id).filter(email=email).exists():
            messages.error(request, 'Email already exists.')
        else:
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.is_active = is_active
            password = request.POST.get('password', '')
            if password:
                user.set_password(password)
            user.save()
            messages.success(request, 'User updated successfully.')
            return redirect('admin_users')
    return render(request, 'dashboards/edit_user.html', {'user': user})

@login_required(login_url='login')
def delete_user(request, user_id):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import User
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully.')
        return redirect('admin_users')
    return render(request, 'dashboards/delete_user.html', {'user': user})


@login_required(login_url='login')
def admin_users(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import User
    users = User.objects.all().order_by('username')
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip()
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    users = users.order_by('username')
    context = {
        'users': users,
        'search_query': search_query,
        'role_filter': role_filter,
        'role_choices': User._meta.get_field('role').choices,
    }
    return render(request, 'dashboards/admin_users.html', context)

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
        # --- AUTOMATIC PROMOTION LOGIC ---
        # If today is after the last term's end_date and promotion not yet run for this year, trigger promotion
        if terms and terms[-1].end_date and today > terms[-1].end_date:
            # Use a session or db flag to avoid repeated promotions for same year
            last_promo_year = request.session.get('last_promo_year')
            if last_promo_year != year.year:
                import subprocess
                import sys
                result = subprocess.run([sys.executable, 'manage.py', 'promote_students'], capture_output=True, text=True)
                if result.returncode == 0:
                    from django.contrib import messages
                    messages.success(request, f'Promotion and graduation process completed automatically for {year.year}.')
                    request.session['last_promo_year'] = year.year
                else:
                    from django.contrib import messages
                    messages.error(request, f'Automatic promotion failed for {year.year}: ' + result.stderr)
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
    import json
    from django.db.models import Sum, Avg
    if request.user.role != 'admin':
        return redirect('dashboard')
    from .models import Subject, Grade, FeeCategory, FeeAssignment, FeePayment, Student, Term
    subjects = Subject.objects.all()
    avg_performance = []
    for subject in subjects:
        avg_score = Grade.objects.filter(subject=subject).aggregate(avg=Avg('score'))['avg']
        avg_performance.append({'subject': subject.name, 'avg_score': avg_score or 0})
    subject_labels = json.dumps([item['subject'] for item in avg_performance])
    avg_scores = json.dumps([item['avg_score'] for item in avg_performance])

    # --- Fee Analytics Section ---
    # Get current term (by date range)
    today = timezone.now().date()
    current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.filter(start_date__lte=today, end_date__isnull=True).order_by('-start_date').first()
    if not current_term:
        current_term = Term.objects.order_by('-start_date').first()
    all_students = Student.objects.all()
    all_fee_categories = FeeCategory.objects.all()
    # Fetch all fee assignments in the system (total billed on all students)
    fee_assignments = FeeAssignment.objects.all()

    # Calculate total assigned as the sum of (amount * number of students in class) for all assignments
    total_assigned = 0
    for assignment in fee_assignments:
        num_students = Student.objects.filter(class_group=assignment.class_group).count()
        total_assigned += float(assignment.amount) * num_students
    total_paid = FeePayment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
    payment_percentage = (float(total_paid) / float(total_assigned) * 100) if total_assigned else 0

    # Pie chart: Paid vs Unpaid
    paid_value = float(total_paid)
    unpaid_value = float(total_assigned) - float(total_paid)
    pie_labels = json.dumps(["Paid", "Unpaid"])
    pie_data = json.dumps([paid_value, unpaid_value if unpaid_value > 0 else 0])

    # Bar chart: Payments over time (by month)
    from collections import defaultdict
    import calendar
    payments = FeePayment.objects.filter(fee_assignment__in=fee_assignments)
    monthly_totals = defaultdict(float)
    for payment in payments:
        month = payment.payment_date.strftime('%Y-%m')
        monthly_totals[month] += float(payment.amount_paid)
    months_sorted = sorted(monthly_totals.keys())
    bar_labels = json.dumps(months_sorted)
    bar_data = json.dumps([monthly_totals[m] for m in months_sorted])

    context = {
        'avg_performance': avg_performance,
        'subject_labels': subject_labels,
        'avg_scores': avg_scores,
        'total_assigned': total_assigned,
        'total_paid': total_paid,
        'payment_percentage': round(payment_percentage, 2),
        'pie_labels': pie_labels,
        'pie_data': pie_data,
        'bar_labels': bar_labels,
        'bar_data': bar_data,
        'current_term': current_term,
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
    subject_grades = {}
    from .models import Exam, Grade
    for assignment in assignments:
        students = Student.objects.filter(class_group=assignment.class_group)
        subject_students[(assignment.subject, assignment.class_group)] = students

        # Get latest exam for this class level
        latest_exam = Exam.objects.filter(level=assignment.class_group.level).order_by('-date').first()
        grades_map = {}
        if latest_exam:
            grades = Grade.objects.filter(exam=latest_exam, subject=assignment.subject, student__in=students)
            for grade in grades:
                grades_map[grade.student_id] = grade

        # Use nested dictionary instead of tuple key
        if assignment.subject.id not in subject_grades:
            subject_grades[assignment.subject.id] = {}
        subject_grades[assignment.subject.id][assignment.class_group.id] = {'exam': latest_exam, 'grades': grades_map}
    # Get subject_id and class_id from query params to show specific table
    show_subject_id = request.GET.get('subject_id')
    show_class_id = request.GET.get('class_id')

    context = {
        'teacher': teacher,
        'subject_students': subject_students,
        'subject_grades': subject_grades,
        'show_subject_id': show_subject_id,
        'show_class_id': show_class_id,
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

@login_required(login_url='login')
def admin_teachers(request):
    teachers = Teacher.objects.all()
    form = AddTeacherForm()
    context = {'teachers': teachers, 'form': form}
    return render(request, 'dashboards/admin_teachers.html', context)

@login_required(login_url='login')
def edit_teacher(request, teacher_id):
    return redirect('admin_teachers')

@login_required(login_url='login')
def delete_teacher(request, teacher_id):
    return redirect('admin_teachers')

@login_required(login_url='login')
def admin_fees(request):
    return render(request, 'dashboards/admin_fees.html', {})

@login_required(login_url='login')
def admin_payment(request):
    return render(request, 'dashboards/admin_payment.html', {})

@login_required(login_url='login')
def admin_events(request):
    return render(request, 'dashboards/admin_events.html', {})

@login_required(login_url='login')
def teacher_timetable(request, teacher_id):
    return render(request, 'dashboards/teacher_timetable.html', {})

@login_required(login_url='login')
def student_fees(request):
    return render(request, 'dashboards/student_fees.html', {})


# API and AJAX placeholders
def exam_events_api(request):
    return JsonResponse([], safe=False)

@require_POST
def add_student_ajax(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def add_teacher_ajax(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def add_class_ajax(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def add_subject_ajax(request):
    return JsonResponse({'status': 'ok'})

def events_json(request):
    return JsonResponse([], safe=False)

@require_POST
def event_create(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def event_update(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def event_delete(request):
    return JsonResponse({'status': 'ok'})

def events_feed(request):
    return JsonResponse([], safe=False)

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
                if hasattr(user, 'student'):
                    return redirect('student_profile', student_id=user.student.id)
                else:
                    messages.error(request, 'User not a student.')
                    return redirect('login')
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

    # Grades card support: get selected exam, students, and grades
    selected_exam = None
    students = []
    student_grades = {}
    exam_id = request.GET.get('exam_id')
    if exam_id:
        try:
            selected_exam = Exam.objects.get(id=exam_id)
            # Get all students for the exam's level
            students = Student.objects.filter(class_group__level=selected_exam.level).select_related('user')
            # Get all grades for this exam
            grades = Grade.objects.filter(exam=selected_exam)
            for grade in grades:
                student_grades[grade.student_id] = grade
        except Exam.DoesNotExist:
            selected_exam = None

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