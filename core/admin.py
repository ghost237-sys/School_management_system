from django.contrib import admin
from .models import (
    User, Subject, Class, Teacher, Student, AcademicYear, Term, Exam, Grade,
    TeacherClassAssignment, FeeCategory, FeeAssignment, FeePayment, Notification,
    PeriodSlot, DefaultTimetable, Department
)

admin.site.register(User)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'color')
    list_filter = ('department',)
    search_fields = ('name', 'code')

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    search_fields = ['student__admission_no', 'student__user__username', 'fee_assignment__fee_category__name', 'fee_assignment__class_group__name', 'fee_assignment__term__name', 'amount_paid', 'reference']
    list_display = ['student', 'fee_assignment', 'amount_paid', 'payment_date', 'payment_method', 'reference']
    list_filter = ['fee_assignment__term', 'fee_assignment__class_group', 'fee_assignment__fee_category', 'payment_method']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'user')
    search_fields = ('user__username', 'message')

@admin.register(PeriodSlot)
class PeriodSlotAdmin(admin.ModelAdmin):
    list_display = ('label', 'start_time', 'end_time', 'is_class_slot')
    list_filter = ('is_class_slot',)
    ordering = ('start_time',)

@admin.register(DefaultTimetable)
class DefaultTimetableAdmin(admin.ModelAdmin):
    list_display = ('class_group', 'day', 'period', 'subject', 'teacher')
    list_filter = ('class_group', 'day', 'teacher', 'subject')
    search_fields = ('class_group__name', 'subject__name', 'teacher__user__username')

# Register other models without custom admin classes
admin.site.register(Class)
admin.site.register(Teacher)
admin.site.register(Student)
admin.site.register(AcademicYear)
admin.site.register(Term)
admin.site.register(Exam)
admin.site.register(Grade)
admin.site.register(TeacherClassAssignment)
admin.site.register(FeeCategory)
admin.site.register(FeeAssignment)
admin.site.register(Department)
