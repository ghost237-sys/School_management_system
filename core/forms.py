from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Teacher, Department, Subject, Class, Student, Exam, Event, FeeCategory, FeeAssignment, FeePayment, Term, Grade

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'term', 'level', 'date', 'type']


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
    birthdate = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))

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
        email = self.cleaned_data['email']
        qs = User.objects.filter(email=email)
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Email already exists.')
        return email

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
        fields = ['first_name', 'last_name', 'username', 'password', 'admission_no', 'class_group', 'gender', 'birthdate']

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = User.objects.filter(email=email)
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Email already exists.')
        return email

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

class FeeAssignmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the term dropdown uses the __str__ method (term name & year)
        self.fields['term'].queryset = self.fields['term'].queryset.select_related('academic_year')
        self.fields['term'].label_from_instance = lambda obj: str(obj)

    class Meta:
        model = FeeAssignment
        fields = ['fee_category', 'class_group', 'term', 'amount']

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
        qs = User.objects.filter(email=email)
        # Exclude current user when editing
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Email already exists.')
        return email
