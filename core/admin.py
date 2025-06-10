from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Subject)
admin.site.register(Class)
admin.site.register(Teacher)
admin.site.register(Student)
admin.site.register(AcademicYear)
admin.site.register(Term)
admin.site.register(Exam)
admin.site.register(Grade)
admin.site.register(TeacherClassAssignment)
