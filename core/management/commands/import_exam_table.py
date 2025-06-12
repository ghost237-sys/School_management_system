from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Student, Subject, Grade, Exam, Term, AcademicYear, Class, Teacher, TeacherClassAssignment
from django.utils import timezone

# Table data (example, you can expand or load from CSV)
DATA = [
    {"name": "Prudence Waru", "LAN": 21, "COM": 84, "ENG": 80, "LUG": 15, "INS": 76, "KIS": 90, "MAT": 72, "SC_TELAG_NLC_A": 83, "SS": 24, "CRE": 87, "TOTAL": 646},
    {"name": "Avril Nelima", "LAN": 70, "COM": 80, "ENG": 73, "LUG": None, "INS": 84, "KIS": 80, "MAT": None, "SC_TELAG_NLC_A": 87, "SS": None, "CRE": None, "TOTAL": 640},
    # ... Add the rest of your data here
]

SUBJECTS = [
    ("Mathematics", "MAT"),
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

DEFAULT_PASSWORD = "student1234"
EXAM_NAME = "Opener exams for grade 6"
TERM_NAME = "Term 1"
YEAR = "2025"

class Command(BaseCommand):
    help = "Import exam table data and create users, students, and grades."

    def handle(self, *args, **kwargs):
        User = get_user_model()
        # Create subjects if not exist
        for subject_name, code in SUBJECTS:
            Subject.objects.get_or_create(name=subject_name, code=code)
        self.stdout.write(self.style.SUCCESS("Subjects ensured."))

        # AcademicYear, Term, Exam
        academic_year, _ = AcademicYear.objects.get_or_create(year=YEAR)
        term, _ = Term.objects.get_or_create(name=TERM_NAME, academic_year=academic_year)
        exam, _ = Exam.objects.get_or_create(name=EXAM_NAME, term=term, defaults={'date': timezone.now().date()})

        # Subject code map
        subject_map = {s.code: s for s in Subject.objects.all()}

        # Ensure the class exists (now 6W)
        class_name = "6W"
        class_level = "6"
        class_obj, _ = Class.objects.get_or_create(name=class_name, level=class_level)

        # Ensure teacher Soye exists
        teacher_username = "soye"
        teacher_user, created = User.objects.get_or_create(username=teacher_username, defaults={
            'email': 'soye@school.local', 'role': 'teacher', 'first_name': 'Soye', 'last_name': 'Teacher'
        })
        if created:
            teacher_user.set_password(DEFAULT_PASSWORD)
            teacher_user.save()
        teacher_obj, _ = Teacher.objects.get_or_create(user=teacher_user)

        # Assign all relevant subjects to Soye
        all_subjects = Subject.objects.filter(code__in=[code for _, code in SUBJECTS])
        teacher_obj.subjects.set(all_subjects)

        for i, entry in enumerate(DATA):
            name = entry["name"].strip()
            if not name:
                continue
            username = name.lower().replace(" ", "_")
            user, created = User.objects.get_or_create(username=username, defaults={
                'email': f'{username}@school.local',
                'role': 'student'
            })
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
            from datetime import date
            admission_no = f"ADM{str(i+1).zfill(3)}"
            student, _ = Student.objects.get_or_create(
                user=user,
                defaults={
                    'birthdate': date(2012, 1, 1),
                    'gender': 'N/A',
                    'admission_no': admission_no,
                    'class_group': class_obj
                }
            )
            # Always update class_group in case student existed
            student.class_group = class_obj
            student.save()
            # Add grades
            for code in ["LAN", "COM", "ENG", "LUG", "INS", "KIS", "MAT", "SC_TELAG_NLC_A", "SS", "CRE"]:
                score = entry.get(code)
                if score is not None and score != "":
                    subject = subject_map.get(code)
                    if subject:
                        Grade.objects.update_or_create(
                            student=student, exam=exam, subject=subject,
                            defaults={"score": score}
                        )
        # Assign Soye to teach all subjects in this class
        for subject in all_subjects:
            TeacherClassAssignment.objects.get_or_create(
                teacher=teacher_obj,
                class_group=class_obj,
                subject=subject
            )

        # Set all students' class_group to 6W
        Student.objects.update(class_group=class_obj)
        # Set Soye as class teacher for 6W
        class_obj.class_teacher = teacher_obj
        class_obj.save()
        self.stdout.write(self.style.SUCCESS("All students assigned to 6W and Soye set as class teacher."))
