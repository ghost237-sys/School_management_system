from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from . import views, views_admin_messaging, views_finance_messaging
from . import views_lock
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static

from .views import timetable_view
from . import timetable_urls

from core.views_student_messaging import student_messaging
from core.views_teacher_messaging import teacher_messaging
from core.views_clerk_messaging import clerk_messaging
urlpatterns = [
    path('', include('core.urls_payment_verification')),
    path('mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),
  path('mpesa/c2b/validation/', views.mpesa_c2b_validation, name='mpesa_c2b_validation'),
  path('mpesa/c2b/confirmation/', views.mpesa_c2b_confirmation, name='mpesa_c2b_confirmation'),
    # Redirect custom admin-like paths BEFORE django admin catch-all
  path('admin/period-slots/', RedirectView.as_view(url='/admin_period_slots/', permanent=False)),
  path('admin/fees/mpesa/reconcile/', views.admin_mpesa_reconcile, name='admin_mpesa_reconcile'),
  path('admin/fees/mpesa/ledger/', views.admin_c2b_ledger, name='admin_c2b_ledger'),
  path('admin/fees/mpesa/', views.admin_mpesa_all, name='admin_mpesa_all'),
  path('admin/fees/mpesa/log-file/', views.admin_payment_log_file, name='admin_payment_log_file'),
  # Custom admin-like view for block result slip must come BEFORE Django admin catch-all
  path('admin/block_result_slip/', views.admin_block_result_slip, name='admin_block_result_slip'),
  path('admin/', admin.site.urls),
    path('api/', include('core.timetable_urls')),
    path('timetable/', timetable_view, name='timetable_view'),
    path('timetable/auto-generate/', views.timetable_auto_generate, name='timetable_auto_generate'),
    path('timetable/school-day/', views.school_timetable_day, name='school_timetable_day'),
    # ... other patterns ...
    path('student_messaging/', student_messaging, name='student_messaging'),
    path('teacher_messaging/', teacher_messaging, name='teacher_messaging'),
    path('clerk_messaging/', clerk_messaging, name='clerk_messaging'),
    path('finance_messaging/', views_finance_messaging.finance_messaging_page, name='finance_messaging_page'),

    # General Login/Logout
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    # Auth utility endpoints
    path('auth/verify-password/', views_lock.verify_password, name='verify_password'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', include('landing.urls')),


    # Admin URLs
    path('admin_overview/', views.admin_overview, name='admin_overview'),
    path('clerk_overview/', views.clerk_overview, name='clerk_overview'),
    # Backward-compat/avoid confusion: redirect old path to new route
    path('admin/website-settings/', RedirectView.as_view(url='/admin_website_settings/', permanent=False)),
    path('admin_website_settings/', views.admin_website_settings, name='admin_website_settings'),
    path('dashboard/website-settings/', views.admin_website_settings, name='admin_website_settings_alt'),
    path('admin_gallery/', views.admin_gallery, name='admin_gallery'),
    path('admin_categories/', views.admin_categories, name='admin_categories'),
    path('admin_users/', views.admin_users, name='admin_users'),
    path('admin_users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('admin_users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin_teachers/', views.admin_teachers, name='admin_teachers'),
    path('admin_teachers/edit/<int:teacher_id>/', views.edit_teacher, name='edit_teacher'),
    path('admin_teachers/delete/<int:teacher_id>/', views.delete_teacher, name='delete_teacher'),
    path('admin_assign_responsibility/', views.admin_assign_responsibility, name='admin_assign_responsibility'),
    path('admin_students/', views.admin_students, name='admin_students'),
    path('admin_graduated_students/', views.admin_graduated_students, name='admin_graduated_students'),
    path('admin_classes/', views.admin_classes, name='admin_classes'),
    path('admin_class_result_slip/<int:class_id>/', views.admin_class_result_slip, name='admin_class_result_slip'),
    path('overall_student_results/<int:class_id>/', views.overall_student_results, name='overall_student_results'),
    path('class_profile/<int:class_id>/', views.class_profile, name='class_profile'),
    path('edit_class/<int:class_id>/', views.edit_class, name='edit_class'),
    path('assign_subject_teachers/<int:class_id>/', views.assign_subject_teachers, name='assign_subject_teachers'),
    path('manage_class_subjects/<int:class_id>/', views.manage_class_subjects, name='manage_class_subjects'),
    path('delete_class/<int:class_id>/', views.delete_class, name='delete_class'),
    path('admin_analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin_analytics/data/', views.admin_analytics_data, name='admin_analytics_data'),
    path('finance/analytics/', views.finance_analytics, name='finance_analytics'),
    path('attendance/view/', views.view_attendance, name='view_attendance'),
    path('admin_subjects/', views.admin_subjects, name='admin_subjects'),
    path('admin_grade_comments/', views.admin_grade_comments, name='admin_grade_comments'),
    path('admin_subject_components/', views.admin_subject_components, name='admin_subject_components'),
    path('manage_subject_grading/<int:subject_id>/', views.manage_subject_grading, name='manage_subject_grading'),
    path('admin_academic_years/', views.admin_academic_years, name='admin_academic_years'),
    # Use a non-admin prefix to avoid being captured by Django admin URLs
    path('admin_period_slots/', views.admin_period_slots, name='admin_period_slots'),
    path('admin_exams/', views.admin_exams, name='admin_exams'),
    path('admin_exams/delete/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('admin_exams/<int:exam_id>/publish/', views.publish_exam_results, name='publish_exam_results'),
    path('admin_exams/<int:exam_id>/unpublish/', views.unpublish_exam_results, name='unpublish_exam_results'),
    # Signed PDF download for student result slips
    path('results/slip/<str:token>/', views.download_result_slip_signed, name='download_result_slip_signed'),
    path('admin_manage_grades/', views.admin_manage_grades_entry, name='admin_manage_grades_entry'),
    path('api/exams/', views.exam_calendar_api, name='exam_calendar_api'),
    path('api/classes/', views.api_classes, name='api_classes'),
    path('api/subjects/', views.api_subjects, name='api_subjects'),
    path('api/students/<int:class_id>/', views.api_students_by_class, name='api_students_by_class'),
    path('api/exam/<int:exam_id>/subjects/', views.api_exam_subjects, name='api_exam_subjects'),
    path('api/bulk-grades/', views.api_bulk_grades, name='api_bulk_grades'),
    path('api/upload-bulk-grades/', views.api_upload_bulk_grades, name='api_upload_bulk_grades'),
    path('api/download-grade-template/', views.api_download_grade_template, name='api_download_grade_template'),
    path('api/download-class-students/<int:class_id>/', views.api_download_class_students, name='api_download_class_students'),
    path('admin_exams/json/', views.admin_exams_json, name='admin_exams_json'),
    path('admin_fees/', views.admin_fees, name='admin_fees'),
    path('admin_fees/history/partial/', views.admin_payment_history_partial, name='admin_payment_history_partial'),
    path('admin_students/partial/', views.admin_students_partial, name='admin_students_partial'),
    path('admin_classes/partial/', views.admin_classes_partial, name='admin_classes_partial'),
    path('admin_exams/available/partial/', views.admin_exams_available_partial, name='admin_exams_available_partial'),
    path('admin_payment/', views.admin_payment, name='admin_payment'),
    path('admin_payment_logs/', views_admin_messaging.admin_payment_logs, name='admin_payment_logs'),
    path('admin_messaging/', views_admin_messaging.admin_messaging, name='admin_messaging'),
    path('admin_messaging/get_users_by_category/', views_admin_messaging.get_users_by_category, name='get_users_by_category'),
    path('admin_messaging/load_messages/', views_admin_messaging.load_messages, name='admin_load_messages'),
    path('admin_messaging/mark_read/', views_admin_messaging.mark_read, name='admin_mark_read'),
    path('admin_messaging/conversation_action/', views_admin_messaging.conversation_action, name='admin_conversation_action'),
    path('admin_events/', views.admin_events, name='admin_events'),
    path('downloads/', views.downloads, name='downloads'),
    # Export/Downloads API (Admin)
    path('exports/users.csv', views.export_users_csv, name='export_users_csv'),
    path('exports/users.pdf', views.export_users_pdf, name='export_users_pdf'),
    path('exports/teachers.csv', views.export_teachers_csv, name='export_teachers_csv'),
    path('exports/teachers.pdf', views.export_teachers_pdf, name='export_teachers_pdf'),
    path('exports/students.csv', views.export_students_csv, name='export_students_csv'),
    path('exports/students.pdf', views.export_students_pdf, name='export_students_pdf'),
    path('exports/fee-assignments.csv', views.export_fee_assignments_csv, name='export_fee_assignments_csv'),
    path('exports/fee-assignments.pdf', views.export_fee_assignments_pdf, name='export_fee_assignments_pdf'),
    path('exports/fee-payments.csv', views.export_fee_payments_csv, name='export_fee_payments_csv'),
    path('exports/fee-payments.pdf', views.export_fee_payments_pdf, name='export_fee_payments_pdf'),
    path('exports/students-with-arrears.csv', views.export_students_with_arrears_csv, name='export_students_with_arrears_csv'),
    path('exports/students-with-arrears.pdf', views.export_students_with_arrears_pdf, name='export_students_with_arrears_pdf'),
    path('exports/students-without-arrears.csv', views.export_students_without_arrears_csv, name='export_students_without_arrears_csv'),
    path('exports/students-without-arrears.pdf', views.export_students_without_arrears_pdf, name='export_students_without_arrears_pdf'),
    path('exports/result-slip.csv', views.export_result_slip_csv, name='export_result_slip_csv'),
    path('exports/result-slip.pdf', views.export_result_slip_pdf, name='export_result_slip_pdf'),
    path('exports/empty-subject-list.csv', views.export_empty_subject_list_csv, name='export_empty_subject_list_csv'),
    path('exports/empty-subject-list.pdf', views.export_empty_subject_list_pdf, name='export_empty_subject_list_pdf'),
    path('admin_send_bulk_arrears_notice/', views_admin_messaging.send_bulk_fee_arrears_notice, name='admin_send_bulk_arrears_notice'),
    path('admin_payment_messages/', views_admin_messaging.admin_payment_messages, name='admin_payment_messages'),
    path('admin_payment_messages/logs/', views_admin_messaging.admin_payment_logs, name='admin_payment_logs'),

    # Teacher URLs
    path('teacher_class_result_slip/<int:class_id>/', views.teacher_class_result_slip, name='teacher_class_result_slip'),
    path('teacher_dashboard/<int:teacher_id>/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher_messaging/', teacher_messaging, name='teacher_messaging'),
    path('teacher/<int:teacher_id>/profile/', views.teacher_profile, name='teacher_profile'),
    path('teacher/<int:teacher_id>/timetable/', views.teacher_timetable, name='teacher_timetable'),
    path('teacher/<int:teacher_id>/attendance/', views.manage_attendance, name='manage_attendance'),
    path('teacher/<int:teacher_id>/attendance/<int:class_id>/<int:subject_id>/', views.take_attendance, name='take_attendance'),
    path('teacher/<int:teacher_id>/grades/', views.manage_grades, name='manage_grades'),
    path('teacher/<int:teacher_id>/grades/<int:class_id>/<int:subject_id>/<int:exam_id>/', views.input_grades, name='input_grades'),
    path('teacher/<int:teacher_id>/results/<int:class_id>/<int:subject_id>/<int:exam_id>/', views.exam_results, name='exam_results'),
    path('teacher/<int:teacher_id>/upload-grades/', views.upload_grades, name='upload_grades'),
    path('teacher/<int:teacher_id>/gradebook/', views.gradebook, name='gradebook'),

    # Student URLs
    path('student_profile/<int:student_id>/', views.student_profile, name='student_profile'),
    path('student_dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student_fees/', views.student_fees, name='student_fees'),
    path('results/blocked/', views.student_results_blocked, name='student_results_blocked'),
    path('fees/paybill/', views.paybill_start, name='paybill_start'),
    path('fees/paybill/status/<str:checkout_request_id>/', views.paybill_status, name='paybill_status'),

    # API and AJAX URLs
    path('api/exam_events/', views.exam_events_api, name='exam_events_api'),
    path('api/job-status/<int:job_id>/', views.job_status, name='job_status'),
    path('dashboard/students/add/', views.add_student_ajax, name='add_student_ajax'),
    path('dashboard/teachers/add/', views.add_teacher_ajax, name='add_teacher_ajax'),
    path('dashboard/classes/add/', views.add_class_ajax, name='add_class_ajax'),
    path('dashboard/subjects/add/', views.add_subject_ajax, name='add_subject_ajax'),
    path('dashboard/events/json/', views.events_json, name='events_json'),
    path('dashboard/events/create/', views.event_create, name='event_create'),
    path('dashboard/events/update/', views.event_update, name='event_update'),
    path('dashboard/events/delete/', views.event_delete, name='event_delete'),
    path('dashboard/events/feed/', views.events_feed, name='events_feed'),
    # Debug-only preview for 404 page (safe to leave; it checks DEBUG at runtime)
    path('_preview/404/', views.preview_404, name='preview_404'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

