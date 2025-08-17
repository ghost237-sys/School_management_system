from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.contrib.auth.forms import UserCreationForm
from .models import User, Teacher, Department, Subject, Class, Student, Exam, Event, FeeCategory, FeeAssignment, FeePayment, Term, Grade, DefaultTimetable, TeacherResponsibility

USER_CATEGORY_CHOICES = [
    ('admin', 'Admin'),
    ('teacher', 'Teacher'),
    ('student', 'Student'),
]

class MessagingForm(forms.Form):
    min_balance = forms.DecimalField(label='Minimum Balance', required=False, min_value=0, decimal_places=2, max_digits=10)
    max_balance = forms.DecimalField(label='Maximum Balance', required=False, min_value=0, decimal_places=2, max_digits=10)
    class_group = forms.ModelChoiceField(label='Class', queryset=Class.objects.all(), required=False)
    recipient = forms.ModelMultipleChoiceField(queryset=User.objects.none(), label='Recipients', required=True, widget=forms.SelectMultiple(attrs={'class': 'form-control'}))
    subject = forms.CharField(max_length=255, label='Subject/Title', required=True, initial='Fee Balance Notification', widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    message = forms.CharField(
    widget=forms.Textarea(attrs={'rows':4, 'readonly': 'readonly'}),
    label='Message',
    required=True,
    initial='Dear Parent/Guardian,\n\nOur records indicate that {student_name} (Admission No: {admission_no}) has an outstanding fee balance of Ksh. {fee_balance}. Kindly clear the arrears at your earliest convenience.\n\nThank you.\nSchool Administration'
)
    send_email = forms.BooleanField(label='Send Email', required=False, initial=True)
    send_sms = forms.BooleanField(label='Send SMS', required=False, initial=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import User, Student, FeeAssignment, FeePayment, Term, Class
        from django.utils import timezone
        from django.db.models import Sum

        today = timezone.now().date()
        current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
        students = Student.objects.select_related('user', 'class_group')

        min_balance = self.data.get('min_balance')
        max_balance = self.data.get('max_balance')
        class_group = self.data.get('class_group')

        students_with_balance = []
        for student in students:
            if class_group and str(student.class_group_id) != str(class_group):
                continue
            fee_assignments = FeeAssignment.objects.filter(class_group=student.class_group)
            total_billed = fee_assignments.aggregate(total=Sum('amount'))['total'] or 0
            total_paid = FeePayment.objects.filter(student=student).aggregate(total=Sum('amount_paid'))['total'] or 0
            balance = total_billed - total_paid
            if balance <= 0:
                continue
            if min_balance and balance < float(min_balance):
                continue
            if max_balance and balance > float(max_balance):
                continue
            students_with_balance.append(student.user.id)
        self.fields['recipient'].queryset = User.objects.filter(id__in=students_with_balance).order_by('username')

from django import forms

LEVEL_CHOICES = [
    ('all', 'All Levels'),
    ('lower', 'Lower Primary (1-3)'),
    ('upper', 'Upper Primary (4-6)'),
    ('junior', 'Junior Secondary (6-9)'),
    ('1', 'Level 1'),
    ('2', 'Level 2'),
    ('3', 'Level 3'),
    ('4', 'Level 4'),
    ('5', 'Level 5'),
    ('6', 'Level 6'),
    ('7', 'Level 7'),
    ('8', 'Level 8'),
    ('9', 'Level 9'),
]

class ExamForm(forms.ModelForm):
    level = forms.MultipleChoiceField(
        choices=LEVEL_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True,
        label='Level(s)'
    )
    class Meta:
        model = Exam
        fields = ['name', 'term', 'level', 'start_date', 'end_date', 'type']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

"""
Composite Subject Management
"""
from .models import SubjectComponent  # local import to avoid disturbing earlier imports


class SubjectComponentForm(forms.ModelForm):
    class Meta:
        model = SubjectComponent
        fields = ['child', 'weight']
        widgets = {
            'child': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class SubjectComponentBaseFormSet(BaseInlineFormSet):
    """
    Filters the child Subject choices so that any Subject already used anywhere
    (as a parent or as a child) is excluded globally, except:
      - the currently selected parent (instance) itself is allowed to stay selected as parent
      - the parent's existing children remain available so they can be edited
    """
    def __init__(self, *args, **kwargs):
        from .models import Subject, SubjectComponent
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Collect all subjects that are already in any relationship
        used_parent_ids = set(SubjectComponent.objects.values_list('parent_id', flat=True))
        used_child_ids = set(SubjectComponent.objects.values_list('child_id', flat=True))
        used_ids = used_parent_ids.union(used_child_ids)

        # Allow editing current parent and its existing children
        if self.instance and getattr(self.instance, 'pk', None):
            used_ids.discard(self.instance.pk)
            current_children = set(
                SubjectComponent.objects.filter(parent=self.instance).values_list('child_id', flat=True)
            )
            used_ids = used_ids.difference(current_children)

        allowed_qs = Subject.objects.exclude(id__in=used_ids)

        for form in self.forms:
            if 'child' in form.fields:
                form.fields['child'].queryset = allowed_qs


# Inline formset to edit components of a selected parent Subject
SubjectComponentFormSet = inlineformset_factory(
    parent_model=Subject,
    model=SubjectComponent,
    form=SubjectComponentForm,
    formset=SubjectComponentBaseFormSet,
    fields=['child', 'weight'],
    fk_name='parent',
    extra=3,
    can_delete=True
)


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'start', 'end', 'all_day', 'is_done', 'comment', 'term', 'category']
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'all_day': forms.CheckboxInput(),
            'is_done': forms.CheckboxInput(),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

class AddSubjectForm(forms.ModelForm):
    name = forms.CharField(max_length=100, required=True, label='Subject Name')
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True, label='Department')

    class Meta:
        model = Subject
        fields = ['name', 'department']


    class_group = forms.ModelChoiceField(queryset=Class.objects.all(), widget=forms.HiddenInput())
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Assign Subjects'
    )

    def __init__(self, *args, **kwargs):
        class_group = kwargs.pop('class_group', None)
        super().__init__(*args, **kwargs)
        if class_group:
            self.fields['class_group'].initial = class_group.id
        # Optionally filter subjects by department or other logic here

    def save(self):
        class_group = self.cleaned_data['class_group']
        subjects = self.cleaned_data['subjects']
        # Remove existing assignments if using M2M or a through model
        class_group.subject_set.set(subjects)
        return class_group

class EditTermDatesForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class AddClassForm(forms.ModelForm):
    LEVEL_CHOICES = [(str(i), f"{i}") for i in range(1, 10)]
    STREAM_CHOICES = [
        ("East", "East"),
        ("West", "West"),
        ("North", "North"),
        ("South", "South"),
    ]

    level = forms.ChoiceField(choices=LEVEL_CHOICES, required=True, label='Level (1-9)')
    stream = forms.ChoiceField(choices=STREAM_CHOICES, required=True, label='Stream')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Class, Teacher
        assigned_teacher_ids = Class.objects.exclude(class_teacher=None).values_list('class_teacher', flat=True)
        self.fields['class_teacher'].queryset = Teacher.objects.exclude(id__in=assigned_teacher_ids)
        self.fields['class_teacher'].label_from_instance = lambda obj: obj.user.get_full_name() if hasattr(obj.user, 'get_full_name') and obj.user.get_full_name() else obj.user.username

    class_teacher = forms.ModelChoiceField(queryset=Teacher.objects.none(), required=False, label='Class Teacher')

    class Meta:
        model = Class
        fields = ['level', 'stream', 'class_teacher']

    def save(self, commit=True):
        instance = super().save(commit=False)
        level = self.cleaned_data['level']
        stream = self.cleaned_data['stream']
        instance.name = f"Grade {level} {stream}"
        instance.level = level
        if commit:
            instance.save()
            self.save_m2m()
        return instance

# class TimeTableSlotForm(forms.ModelForm):
#     class Meta:
#         model = TimeTableSlot
#         fields = ['day_of_week', 'start_time', 'end_time', 'class_group', 'subject', 'teacher', 'term']
#         widgets = {
#             'start_time': forms.TimeInput(attrs={'type': 'time'}),
#             'end_time': forms.TimeInput(attrs={'type': 'time'}),
#         }

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'role')  # Add others as needed

class AddStudentForm(forms.ModelForm):
    def save_user(self):
        from .models import User
        cleaned = self.cleaned_data
        user = User.objects.create_user(
            username=cleaned['username'],
            email=cleaned['email'],
            password=cleaned['password'],
            first_name=cleaned['first_name'],
            last_name=cleaned['last_name'],
            role='student',
            is_active=True
        )
        return user

    # User fields
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    # Student fields
    admission_no = forms.CharField(max_length=20, required=True)
    class_group = forms.ModelChoiceField(queryset=Class.objects.all(), required=True)
    gender = forms.ChoiceField(choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], required=True)
    birthdate = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)

    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'admission_no', 'class_group', 'gender', 'birthdate']

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        # Students are allowed to share emails
        return self.cleaned_data.get('email')

class StudentContactUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label='Email Address')
    phone = forms.CharField(max_length=20, required=False, label='Phone Number')
    postal_address = forms.CharField(max_length=255, required=False, label='Postal Address')

    class Meta:
        model = Student
        fields = ['phone', 'postal_address']

    def __init__(self, *args, **kwargs):
        user_instance = kwargs.pop('user_instance', None)
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
        if self.instance:
            self.fields['phone'].initial = self.instance.phone
            self.fields['postal_address'].initial = getattr(self.instance, 'postal_address', '')

    def save(self, commit=True):
        student = super().save(commit=False)
        if self.user_instance:
            self.user_instance.email = self.cleaned_data['email']
            if commit:
                self.user_instance.save()
        if commit:
            student.save()
        return student

class EditStudentClassForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['class_group']

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description']

class GradeUploadForm(forms.Form):
    exam = forms.ModelChoiceField(queryset=Exam.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}))
    subject = forms.ModelChoiceField(queryset=Subject.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}))
    class_group = forms.ModelChoiceField(queryset=Class.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}))
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        self.fields['exam'].queryset = Exam.objects.all()

        if teacher:
            assigned_classes = Class.objects.filter(teacherclassassignment__teacher=teacher).distinct()
            assigned_subjects = Subject.objects.filter(teacherclassassignment__teacher=teacher).distinct()
            self.fields['class_group'].queryset = assigned_classes
            self.fields['subject'].queryset = assigned_subjects

class FeeAssignmentForm(forms.ModelForm):
    class_group = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label='Class Group',
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Class
        self.fields['class_group'].queryset = Class.objects.all()
        # Ensure the term dropdown uses the __str__ method (term name & year)
        self.fields['term'].queryset = self.fields['term'].queryset.select_related('academic_year')
        self.fields['term'].label_from_instance = lambda obj: str(obj)

    class Meta:
        model = FeeAssignment
        fields = ['fee_category', 'term', 'amount']

class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['student', 'amount_paid', 'payment_method', 'reference']

class GradeInputForm(forms.ModelForm):
    admission_no = forms.CharField(disabled=True, required=False)
    gender = forms.CharField(disabled=True, required=False)

    class Meta:
        model = Grade
        fields = ['student', 'exam', 'subject', 'score', 'remarks']

    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.all()
        
        # Add student information fields
        if student:
            self.fields['admission_no'].initial = student.admission_no
            self.fields['gender'].initial = student.gender
            self.fields['student'].label_from_instance = lambda obj: f"{obj.user.get_full_name()} - {obj.admission_no} ({obj.gender})"
        
        # Style the form fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            if field_name == 'score':
                field.widget.attrs.update({'min': '0', 'max': '100', 'step': '0.1'})

class AddTeacherForm(forms.ModelForm):
    def save_user(self):
        from .models import User
        cleaned = self.cleaned_data
        user = User.objects.create_user(
            username=cleaned['username'],
            email=cleaned['email'],
            password=cleaned['password'],
            first_name=cleaned['first_name'],
            last_name=cleaned['last_name'],
            role='teacher',
            is_active=True
        )
        return user

    # User fields
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    # Teacher fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide password field if editing (instance exists and has pk)
        if self.instance and getattr(self.instance, 'pk', None):
            self.fields.pop('password', None)
        # Allow parent or atom subjects; exclude only component (child) subjects
        if 'subjects' in self.fields:
            self.fields['subjects'].queryset = Subject.objects.filter(part_of__isnull=True).order_by('name').distinct()
    tsc_number = forms.CharField(max_length=30, required=False)
    staff_id = forms.CharField(max_length=30, required=False)
    phone = forms.CharField(max_length=20, required=False)
    gender = forms.ChoiceField(choices=Teacher.GENDER_CHOICES, required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'horizontal-checkbox-list'}),
        required=False
    )

    class Meta:
        model = Teacher
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'tsc_number', 'staff_id', 'phone', 'gender', 'department', 'subjects']

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        # Exclude current user when editing
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']

class TeacherProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Teacher
        fields = ['phone']

    def __init__(self, *args, **kwargs):
        user_instance = kwargs.pop('user_instance', None)
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        teacher = super().save(commit=False)
        if self.user_instance:
            self.user_instance.email = self.cleaned_data['email']
            if commit:
                self.user_instance.save()
        if commit:
            teacher.save()
        return teacher
        qs = User.objects.filter(email=email)
        # Exclude current user when editing
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Email already exists.')
        return email


class DefaultTimetableForm(forms.ModelForm):
    class Meta:
        model = DefaultTimetable
        fields = ['subject', 'teacher']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = Teacher.objects.select_related('user').order_by('user__first_name', 'user__last_name')
        # Allow parent or atom subjects; exclude only component (child) subjects
        self.fields['subject'].queryset = Subject.objects.filter(part_of__isnull=True).order_by('name').distinct()
        self.fields['teacher'].required = False


class TeacherResponsibilityForm(forms.ModelForm):
    class Meta:
        model = TeacherResponsibility
        fields = ['teacher', 'responsibility', 'details', 'start_date', 'end_date']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'responsibility': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Teacher on Duty, Games Master, etc.'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional details about the responsibility'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
