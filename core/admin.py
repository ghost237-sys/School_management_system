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
@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = ("checkout_request_id", "status", "amount", "phone_number", "mpesa_receipt", "created_at")
    search_fields = ("checkout_request_id", "mpesa_receipt", "phone_number", "student__admission_no", "student__user__username")
    list_filter = ("status", "created_at")

@admin.register(MpesaC2BLedger)
class MpesaC2BLedgerAdmin(admin.ModelAdmin):
    list_display = ("trans_id", "amount", "msisdn", "bill_ref", "business_short_code", "trans_time", "created_at")
    search_fields = ("trans_id", "msisdn", "bill_ref", "business_short_code")
    list_filter = ("business_short_code", "created_at")
    readonly_fields = ("raw",)
class FeePaymentAdmin(admin.ModelAdmin):
    search_fields = ['student__admission_no', 'student__user__username', 'fee_assignment__fee_category__name', 'fee_assignment__class_group__name', 'fee_assignment__term__name', 'amount_paid', 'reference']
    list_display = ['student', 'fee_assignment', 'amount_paid', 'payment_date', 'payment_method', 'reference']
    list_filter = ['fee_assignment__term', 'fee_assignment__class_group', 'fee_assignment__fee_category', 'payment_method']

admin.site.register(FeePayment, FeePaymentAdmin)

# --- Optional Charges Admin ---
@admin.register(OptionalChargeCategory)
class OptionalChargeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(OptionalOffer)
class OptionalOfferAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "term", "class_group", "amount", "is_active")
    list_filter = ("category", "term", "class_group", "is_active")
    search_fields = ("title", "description")

@admin.register(StudentOptionalCharge)
class StudentOptionalChargeAdmin(admin.ModelAdmin):
    list_display = ("student", "offer", "amount", "status", "created_at")
    list_filter = ("status", "offer__term", "offer__category", "offer__class_group")
    search_fields = ("student__admission_no", "student__user__username", "offer__title")

@admin.register(OptionalChargePayment)
class OptionalChargePaymentAdmin(admin.ModelAdmin):
    list_display = ("student_optional_charge", "amount_paid", "payment_date", "method", "reference")
    list_filter = ("payment_date", "method")
    search_fields = ("reference", "student_optional_charge__student__admission_no")
