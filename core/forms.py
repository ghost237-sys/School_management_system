from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Teacher, Department, Subject, Class, Student

class AddSubjectForm(forms.ModelForm):
    name = forms.CharField(max_length=100, required=True, label='Subject Name')
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True, label='Department')

    class Meta:
        model = Subject
        fields = ['name', 'department']

class AddClassForm(forms.ModelForm):
    name = forms.CharField(max_length=100, required=True, label='Stream Name')
    level = forms.CharField(max_length=50, required=True, label='Year/Level')

    class Meta:
        model = Class
        fields = ['name', 'level']

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'role')  # Add others as needed

class AddStudentForm(forms.ModelForm):
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
        email = self.cleaned_data['email']
        qs = User.objects.filter(email=email)
        if self.instance and getattr(self.instance, 'user_id', None):
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Email already exists.')
        return email

class AddTeacherForm(forms.ModelForm):
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
    class_teacher_of = forms.ModelMultipleChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Teacher
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'tsc_number', 'staff_id', 'phone', 'gender', 'department', 'subjects', 'class_teacher_of']

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
