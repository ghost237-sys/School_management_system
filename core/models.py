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
    subjects = models.ManyToManyField('Subject', blank=True, related_name='classes')

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
    phone = models.CharField(max_length=20, blank=True, null=True)
    postal_address = models.CharField(max_length=255, blank=True, null=True)
    graduated = models.BooleanField(default=False)  # Added for graduation status tracking

    def __str__(self):
        if self.user and (self.user.first_name or self.user.last_name):
            return f"{self.user.first_name} {self.user.last_name}".strip()
        elif self.user:
            return self.user.username
        return f"Student {self.pk}"

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

    def __str__(self):
        return f"{self.name} - {self.academic_year.year}"

class Exam(models.Model):
    EXAM_TYPE_CHOICES = [
        ('opener', 'Opener exams'),
        ('midterm', 'Mid-term exams'),
        ('endterm', 'End-Term exams'),
        ('others', 'Others'),
    ]
    name = models.CharField(max_length=50)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    level = models.CharField(max_length=50, null=True, blank=True)  # E.g., '6' for Grade 6
    date = models.DateField()
    type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES, default='others')

    def __str__(self):
        return f"{self.name} - {self.term.name}"

class Grade(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.FloatField()
    grade_letter = models.CharField(max_length=2, blank=True, null=True)
    remarks = models.TextField(blank=True)

class SubjectGradingScheme(models.Model):
    subject = models.OneToOneField(Subject, on_delete=models.CASCADE, related_name='grading_scheme')
    # Store grade boundaries as a JSON field: e.g. {"A": [80, 100], "B": [70, 79], ...}
    grade_boundaries = models.JSONField(default=dict, help_text="Map of grade letter to [min, max] score, e.g. {'A': [80, 100], 'B': [70, 79]}")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)

    def get_grade_letter(self, score):
        """Return the grade letter for a given score based on boundaries."""
        for letter, (min_score, max_score) in self.grade_boundaries.items():
            if min_score <= score <= max_score:
                return letter
        return None

    def __str__(self):
        return f"Grading Scheme for {self.subject.name}"

# --- Fee Management Models ---

class FeeCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class FeeAssignment(models.Model):
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='assignments')
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='fee_assignments')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='fee_assignments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('fee_category', 'class_group', 'term')

    def __str__(self):
        return f"{self.fee_category} - {self.class_group} - {self.term}"

class FeePayment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_payments')
    fee_assignment = models.ForeignKey(FeeAssignment, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # e.g., cash, bank, mobile money
    reference = models.CharField(max_length=100, blank=True, null=True)  # e.g., transaction ID
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # For Mpesa Paybill

    def __str__(self):
        return f"{self.student} paid {self.amount_paid} for {self.fee_assignment} on {self.payment_date}"

    class Meta:
        ordering = ['-payment_date']

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
    CATEGORY_CHOICES = [
        ('exam', 'Exam Day'),
        ('midterm', 'Mid-Term Break'),
        ('holiday', 'Holiday'),
        ('sports', 'Games/Sports Day'),
        ('other', 'Other'),
    ]
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    all_day = models.BooleanField(default=False)
    is_done = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    term = models.ForeignKey('Term', on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.start:%Y-%m-%d %H:%M})"

# --- Messaging Module ---

class FinanceMessageHistory(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_messages')
    message_content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_messages_sent')
    delivery_method = models.CharField(max_length=10, choices=[('email', 'Email'), ('sms', 'SMS')], default='email')
    status = models.CharField(max_length=20, default='sent')

    def __str__(self):
        return f"To {self.recipient.username} at {self.sent_at:%Y-%m-%d %H:%M}"
class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.sender.username} to {self.recipient.username} at {self.timestamp:%Y-%m-%d %H:%M}"
