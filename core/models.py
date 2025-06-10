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

class Class(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50)
    class_teacher = models.ForeignKey('Teacher', null=True, blank=True, on_delete=models.SET_NULL)

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subjects = models.ManyToManyField(Subject)

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    admission_no = models.CharField(max_length=20, unique=True)
    class_group = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True)
    gender = models.CharField(max_length=10)
    birthdate = models.DateField()

class AcademicYear(models.Model):
    year = models.CharField(max_length=10)

class Term(models.Model):
    name = models.CharField(max_length=20)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

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
