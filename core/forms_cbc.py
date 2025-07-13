from django import forms
from .models import Assessment, StudentAssessment, MarksheetUpload

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['title', 'subject', 'class_level', 'term', 'strand', 'sub_strand', 'date_given', 'assessment_type', 'max_score']

class StudentAssessmentForm(forms.ModelForm):
    class Meta:
        model = StudentAssessment
        fields = ['student', 'assessment', 'grade', 'feedback']

class MarksheetUploadForm(forms.ModelForm):
    class Meta:
        model = MarksheetUpload
        fields = ['student', 'class_level', 'term', 'lan', 'com', 'eng', 'total']
