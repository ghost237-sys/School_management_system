from django.db import models
from django.contrib.auth.models import AbstractUser

# Optional: Extend User model
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='subjects')

    def __str__(self):
        return f"{self.name} ({self.department})" if self.department else self.name

class Class(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50)
    class_teacher = models.ForeignKey('Teacher', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} (Level {self.level})"

class Department(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class Teacher(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tsc_number = models.CharField(max_length=30, blank=True, null=True)
    staff_id = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    subjects = models.ManyToManyField(Subject)

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    admission_no = models.CharField(max_length=20, unique=True)
    class_group = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    gender = models.CharField(max_length=10)
    birthdate = models.DateField()
    graduated = models.BooleanField(default=False)  # Added for graduation status tracking

    @property
    def full_name(self):
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        return self.user.username

    @property
    def is_profile_complete(self):
        return bool(self.user.first_name and self.user.last_name)

class AcademicYear(models.Model):
    year = models.CharField(max_length=10)

class Term(models.Model):
    name = models.CharField(max_length=20)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

class Exam(models.Model):
    name = models.CharField(max_length=50)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    date = models.DateField()

class Grade(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.FloatField()
    grade_letter = models.CharField(max_length=2, blank=True, null=True)
    remarks = models.TextField(blank=True)

class TeacherClassAssignment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('teacher', 'class_group', 'subject')

    def __str__(self):
        return f'{self.teacher} - {self.class_group} - {self.subject}'

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('student', 'subject', 'date')

    def __str__(self):
        return f"{self.student} - {self.subject.name} - {self.date} - {self.status}"

class Deadline(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} for {self.class_group.name} ({self.subject.name})"

class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    all_day = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.start:%Y-%m-%d %H:%M})"
