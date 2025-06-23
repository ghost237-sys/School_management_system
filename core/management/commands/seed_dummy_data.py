from django.core.management.base import BaseCommand
from core.models import User, Teacher, Student, Subject, Class, Department, AcademicYear, Term, Exam, Grade, TeacherClassAssignment
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Seed the database with dummy data for testing.'

    def handle(self, *args, **kwargs):
        # Clear existing data (optional, comment if not desired)
        Grade.objects.all().delete()
        Exam.objects.all().delete()
        Term.objects.all().delete()
        AcademicYear.objects.all().delete()
        TeacherClassAssignment.objects.all().delete()
        Student.objects.all().delete()
        Teacher.objects.all().delete()
        Class.objects.all().delete()
        Subject.objects.all().delete()
        Department.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()

        # Departments
        dept = Department.objects.create(name='Science')

        # Subjects (user's provided list)
        subject_list = [
            ("Kiswahili", "KIS"),
            ("Lugha", "LUG"),
            ("Insha", "INS"),
            ("English", "ENG"),
            ("Language", "LAN"),
            ("Composition", "COM"),
            ("Integrated Science", "SC_TELAG_NLC_A"),
            ("Agriculture", "AGR"),
            ("Art and Craft", "ART"),
            ("Music", "MUS"),
            ("Social Studies", "SS"),
            ("CRE", "CRE"),
            ("Science and Technology", "SCI"),
            ("Agriculture and Nutrition", "AGR_NUT"),
            ("Creative Art", "CRT"),
            ("Pre Tech", "PRE_TECH"),
            ("Technical", "TECH"),
            ("PE", "PE"),
        ]
        subjects = [Subject.objects.create(name=n, code=c) for n, c in subject_list]

        # Academic Year & Term
        year = AcademicYear.objects.create(year='2024/2025')
        term = Term.objects.create(name='Term 1', academic_year=year)

        # Exams
        exam1 = Exam.objects.create(name='Midterm', term=term, date=timezone.now().date())
        exam2 = Exam.objects.create(name='Final', term=term, date=timezone.now().date())

        # Classes
        classes = [Class.objects.create(name=f'Form {i}A', level=str(i)) for i in range(1, 4)]

        # Teachers
        for i in range(2):
            user = User.objects.create_user(username=f'teacher{i+1}', email=f'teacher{i+1}@school.com', password='pass1234', role='teacher')
            teacher = Teacher.objects.create(user=user, department=dept, gender='male' if i % 2 == 0 else 'female')
            teacher.subjects.set(subjects[i:i+3])
            # Assign teacher to classes and subjects
            for c in classes:
                for subj in teacher.subjects.all():
                    TeacherClassAssignment.objects.create(teacher=teacher, class_group=c, subject=subj)

        # Students
        for c in classes:
            for j in range(5):
                user = User.objects.create_user(username=f'student{c.id}{j+1}', email=f'student{c.id}{j+1}@school.com', password='pass1234', role='student')
                student = Student.objects.create(user=user, admission_no=f'ADM{c.id}{j+1}', class_group=c, gender='male' if j % 2 == 0 else 'female', birthdate='2010-01-01')
                # Grades for each subject, exam
                for subj in subjects:
                    for exam in [exam1, exam2]:
                        score = random.randint(30, 100)
                        Grade.objects.create(student=student, exam=exam, subject=subj, score=score, grade_letter=None, remarks='')

        self.stdout.write(self.style.SUCCESS('Dummy data seeded successfully.'))
