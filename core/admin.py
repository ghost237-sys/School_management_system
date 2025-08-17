from django.contrib import admin
from .models import *


class SubjectComponentInline(admin.TabularInline):
    model = SubjectComponent
    fk_name = 'parent'
    extra = 1


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department")
    search_fields = ("name", "code")
    inlines = [SubjectComponentInline]


admin.site.register(User)
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
admin.site.register(Event)
class FeePaymentAdmin(admin.ModelAdmin):
    search_fields = ['student__admission_no', 'student__user__username', 'fee_assignment__fee_category__name', 'fee_assignment__class_group__name', 'fee_assignment__term__name', 'amount_paid', 'reference']
    list_display = ['student', 'fee_assignment', 'amount_paid', 'payment_date', 'payment_method', 'reference']
    list_filter = ['fee_assignment__term', 'fee_assignment__class_group', 'fee_assignment__fee_category', 'payment_method']

admin.site.register(FeePayment, FeePaymentAdmin)
