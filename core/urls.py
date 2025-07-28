from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from .views_admin_messaging import admin_send_message
from . import timetable_urls
from . import views

urlpatterns = [
    # General Login/Logout
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),

    # Admin URLs
    path('admin_overview/', views.admin_overview, name='admin_overview'),
    path('admin_users/', views.admin_users, name='admin_users'),
    path('admin_users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('admin_users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin_teachers/', views.admin_teachers, name='admin_teachers'),
    path('admin_teachers/edit/<int:teacher_id>/', views.edit_teacher, name='edit_teacher'),
    path('admin_teachers/delete/<int:teacher_id>/', views.delete_teacher, name='delete_teacher'),
    path('admin_students/', views.admin_students, name='admin_students'),
    path('admin_classes/', views.admin_classes, name='admin_classes'),
    path('admin_class_result_slip/<int:class_id>/', views.admin_class_result_slip, name='admin_class_result_slip'),
    path('overall_student_results/<int:class_id>/', views.overall_student_results, name='overall_student_results'),
    path('class_profile/<int:class_id>/', views.class_profile, name='class_profile'),
    path('edit_class/<int:class_id>/', views.edit_class, name='edit_class'),
    path('delete_class/<int:class_id>/', views.delete_class, name='delete_class'),
    path('admin_analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin_subjects/', views.admin_subjects, name='admin_subjects'),
    path('admin_academic_years/', views.admin_academic_years, name='admin_academic_years'),
    path('admin_exams/', views.admin_exams, name='admin_exams'),
    path('admin_payment/', views.admin_payment, name='admin_payment'),
    path('admin_fees/', views.admin_fees, name='admin_fees'),
    path('admin_events/', views.admin_events, name='admin_events'),
    path('admin/send-message/', admin_send_message, name='admin_send_message'),

    # Timetable URLs
    path('timetable/', include(timetable_urls)),

    # Teacher URLs
    path('teacher_dashboard/<int:teacher_id>/', views.teacher_dashboard, name='teacher_dashboard'),
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
    path('student_fees/', views.student_fees, name='student_fees'),

    # API and AJAX URLs
    path('api/exam_events/', views.exam_events_api, name='exam_events_api'),
    path('dashboard/students/add/', views.add_student_ajax, name='add_student_ajax'),
    path('dashboard/teachers/add/', views.add_teacher_ajax, name='add_teacher_ajax'),
    path('dashboard/classes/add/', views.add_class_ajax, name='add_class_ajax'),
    path('dashboard/subjects/add/', views.add_subject_ajax, name='add_subject_ajax'),
    path('dashboard/events/json/', views.events_json, name='events_json'),
    path('dashboard/events/create/', views.event_create, name='event_create'),
    path('dashboard/events/update/', views.event_update, name='event_update'),
    path('dashboard/events/delete/', views.event_delete, name='event_delete'),
    path('dashboard/events/feed/', views.events_feed, name='events_feed'),
]

