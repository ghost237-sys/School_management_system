from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# Optional: Extend User model
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('clerk', 'Clerk'),
    ]
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='subjects')
    color = models.CharField(max_length=7, default='#007bff', help_text="Color for the timetable events")
    # Admin-configurable average number of lessons per week for this subject
    weekly_lessons = models.PositiveIntegerField(default=3, help_text="Average/target lessons per week (default 3)")
    # New: Admin-enforced minimum number of lessons per week (scheduler will not go below this)
    min_weekly_lessons = models.PositiveIntegerField(default=3, help_text="Minimum lessons per week to enforce in the timetable (default 3)")

    def __str__(self):
        return f"{self.name} ({self.department})" if self.department else self.name

    @property
    def is_composite(self):
        """Returns True if this subject is defined as a parent with component subjects."""
        return self.subject_components.exists()

    @property
    def is_child(self):
        """Returns True if this subject is a component of another subject."""
        return self.part_of.exists()

    def get_components(self):
        """List of (child_subject, weight) tuples for this parent subject."""
        return [(sc.child, sc.weight) for sc in self.subject_components.select_related('child')]

class Class(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50)
    class_teacher = models.OneToOneField('Teacher', null=True, blank=True, on_delete=models.SET_NULL)
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

    def __str__(self):
        if self.user and (self.user.first_name or self.user.last_name):
            return f"{self.user.first_name} {self.user.last_name}".strip()
        elif self.user:
            return self.user.username
        return f"Teacher {self.pk}"

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

    class Meta:
        indexes = [
            models.Index(fields=['class_group']),
            models.Index(fields=['phone']),
        ]

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
    name = models.CharField(max_length=50, unique=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    level = models.CharField(max_length=50, null=True, blank=True)  # E.g., '6' for Grade 6
    start_date = models.DateField()
    end_date = models.DateField()
    type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES, default='others')
    # Results publication flags
    results_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.term.name}"

    @property
    def is_done(self):
        """Exam considered done if end_date is today or earlier."""
        # timezone imported elsewhere in this module (used by other models)
        from django.utils import timezone
        today = timezone.now().date()
        return bool(self.end_date and self.end_date <= today)

    @property
    def can_publish(self):
        """Convenience: can publish only after it's done and not already published."""
        return self.is_done and not self.results_published

class Grade(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.FloatField()
    grade_letter = models.CharField(max_length=2, blank=True, null=True)
    remarks = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['exam']),
            models.Index(fields=['subject']),
        ]

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

class SubjectComponent(models.Model):
    """
    Defines a composite relationship: parent subject is computed from one or more child subjects.
    By default, parent's score is the sum of its children's scores (optionally weighted).
    """
    parent = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='subject_components')
    child = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='part_of')
    weight = models.FloatField(default=1.0, help_text='Optional weight multiplier for this child when aggregating to parent')

    class Meta:
        unique_together = ('parent', 'child')
        verbose_name = 'Subject Component'
        verbose_name_plural = 'Subject Components'

    def __str__(self):
        return f"{self.parent.name} <= {self.child.name} (w={self.weight})"

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
        indexes = [
            models.Index(fields=['class_group', 'term']),
            models.Index(fields=['term']),
        ]

    def __str__(self):
        return f"{self.fee_category} - {self.class_group} - {self.term}"

class FeePayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_payments')
    fee_assignment = models.ForeignKey(FeeAssignment, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # e.g., cash, bank, mobile money
    reference = models.CharField(max_length=100, blank=True, null=True)  # e.g., transaction ID
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # For Mpesa Paybill
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')  # Verification status

    def __str__(self):
        return f"{self.student} paid {self.amount_paid} for {self.fee_assignment} on {self.payment_date}"

    class Meta:
        ordering = ['-payment_date']
        constraints = [
            models.UniqueConstraint(fields=['reference'], name='unique_mpesa_reference')
        ]
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['fee_assignment']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['status']),
        ]

    # Link back to MpesaTransaction when available (for traceability)
    mpesa_transaction = models.ForeignKey('MpesaTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')

class MpesaTransaction(models.Model):
    """Tracks STK push requests and their lifecycle for verification."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transactions')
    fee_assignment = models.ForeignKey(FeeAssignment, on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transactions')
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    account_reference = models.CharField(max_length=100, blank=True, null=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True, null=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    raw_callback = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MpesaTX {self.checkout_request_id} ({self.status})"

class MpesaC2BLedger(models.Model):
    """Immutable ledger of PayBill (C2B) confirmations.

    Stores raw details from Safaricom so that if the callback handling path
    fails (e.g., network error, URL down), we can reconcile/verify later by
    TransID.
    """
    trans_id = models.CharField(max_length=30, unique=True, db_index=True)
    trans_time = models.CharField(max_length=20, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    msisdn = models.CharField(max_length=20, blank=True, null=True)
    bill_ref = models.CharField(max_length=100, blank=True, null=True)
    business_short_code = models.CharField(max_length=20, blank=True, null=True)
    third_party_trans_id = models.CharField(max_length=64, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    org_account_balance = models.CharField(max_length=100, blank=True, null=True)
    raw = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"C2B {self.trans_id} KES {self.amount or '-'}"

class TeacherClassAssignment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('teacher', 'class_group', 'subject')

    def __str__(self):
        return f'{self.teacher} - {self.class_group} - {self.subject}'

class PeriodSlot(models.Model):
    """Represents a static period or break time slot in a day."""
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=50, help_text='e.g., "Period 1", "Break"')
    is_class_slot = models.BooleanField(default=True, help_text='Is this a slot for a class or a break?')

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.label} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class DefaultTimetable(models.Model):
    """A default timetable structure mapping classes, subjects, and periods."""
    DAY_CHOICES = (
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
    )

    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='timetable_entries')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    period = models.ForeignKey(PeriodSlot, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    editable = models.BooleanField(default=True)

    class Meta:
        unique_together = ('class_group', 'day', 'period')  # Ensures one subject per period per class
        ordering = ['class_group', 'day', 'period__start_time']

    def __str__(self):
        teacher_name = self.teacher.user.get_full_name() if self.teacher else "Not Assigned"
        return f"{self.class_group} | {self.day} | {self.period.label}: {self.subject.name} ({teacher_name})"

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
    timestamp = models.DateTimeField(default=timezone.now)
    period = models.ForeignKey(PeriodSlot, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'date', 'period')

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
class Group(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User, related_name='user_groups')  # Avoids clash with User.groups
    is_category = models.BooleanField(default=False, help_text='True if this is a category group (e.g. all students)')
    category = models.CharField(max_length=20, blank=True, null=True, help_text='student, teacher, parent, etc.')

    def __str__(self):
        return self.name

class BroadcastMessage(models.Model):
    sender = models.ForeignKey(User, related_name='broadcasts_sent', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, related_name='broadcasts')
    recipients = models.ManyToManyField(User, related_name='broadcasts_received', blank=True)
    # If group is set, it's a group broadcast; else, use recipients.

    def __str__(self):
        if self.group:
            return f"Broadcast to {self.group.name} at {self.timestamp:%Y-%m-%d %H:%M}"
        return f"Broadcast to {self.recipients.count()} users at {self.timestamp:%Y-%m-%d %H:%M}"

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    broadcast = models.ForeignKey(BroadcastMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')

    def __str__(self):
        if self.group:
            return f"Group {self.group.name}: {self.sender.username} at {self.timestamp:%Y-%m-%d %H:%M}"
        if self.broadcast:
            return f"Broadcast: {self.sender.username} at {self.timestamp:%Y-%m-%d %H:%M}"
        return f"From {self.sender.username} to {self.recipient.username} at {self.timestamp:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"


class PromotionLog(models.Model):
    last_promoted_year = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Last promoted: {self.last_promoted_year}"


class TeacherResponsibility(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='responsibilities')
    responsibility = models.CharField(max_length=100)
    details = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True, help_text='Start date of the responsibility assignment')
    end_date = models.DateField(null=True, blank=True, help_text='End date of the responsibility assignment')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_responsibilities')
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.teacher.user.get_full_name() if self.teacher.user else self.teacher} - {self.responsibility}"  


class NotificationJob(models.Model):
    """Tracks long-running messaging/notification jobs for fast UI status polling."""
    TYPE_CHOICES = [
        ('exam_publish', 'Exam Publish Notifications'),
        ('fee_arrears', 'Fee Arrears Notifications'),
    ]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued')
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['job_type']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def mark_running(self, total=None):
        if total is not None:
            self.total = total
        self.status = 'running'
        self.save(update_fields=['status', 'total', 'updated_at'])

    def incr(self, success=True, step=1):
        self.processed = models.F('processed') + step
        if success:
            self.success_count = models.F('success_count') + step
        else:
            self.error_count = models.F('error_count') + step
        self.save(update_fields=['processed', 'success_count', 'error_count', 'updated_at'])
        # Refresh from DB to get actual values after F expressions
        return type(self).objects.only('processed', 'success_count', 'error_count').get(pk=self.pk)

    def mark_done(self):
        self.status = 'done'
        self.save(update_fields=['status', 'updated_at'])

    def mark_failed(self, error_msg=None):
        self.status = 'failed'
        if error_msg:
            self.meta = {**(self.meta or {}), 'error': error_msg}
        self.save(update_fields=['status', 'meta', 'updated_at'])


class GradeCommentTemplate(models.Model):
    """
    Admin-configurable comment text to be shown in gradebooks based on grade letter.
    Optionally, this can be extended later to be per-subject or per-level.
    """
    GRADE_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('F', 'F'),
    ]
    grade_letter = models.CharField(max_length=2, choices=GRADE_CHOICES, unique=True)
    comment = models.TextField(help_text='Comment shown in gradebooks for this grade letter')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Grade Comment Template'
        verbose_name_plural = 'Grade Comment Templates'

    def __str__(self):
        return f"{self.grade_letter}: {self.comment[:40]}"


# --- Persistent Result Blocking ---
class ResultBlock(models.Model):
    """Persisted block record for a student's exam results.

    When active=True, the student's result slip for the given exam should be blocked
    across student-facing endpoints until an admin deactivates it.
    """
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='result_blocks')
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='result_blocks')
    active = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True, default='')
    balance_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='created_result_blocks')
    created_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'exam')

    def __str__(self):
        return f"Block(student={self.student_id}, exam={self.exam_id}, active={self.active})"
