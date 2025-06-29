from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('teacher_dashboard/<int:teacher_id>/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/<int:teacher_id>/attendance/', views.manage_attendance, name='manage_attendance'),
    path('teacher/<int:teacher_id>/attendance/<int:class_id>/<int:subject_id>/', views.take_attendance, name='take_attendance'),
    path('teacher/<int:teacher_id>/grades/', views.manage_grades, name='manage_grades'),
    path('teacher/<int:teacher_id>/grades/<int:class_id>/<int:subject_id>/', views.input_grades, name='input_grades'),
    path('teacher_profile/<int:teacher_id>/', views.teacher_profile, name='teacher_profile'),
    path('student_profile/<int:student_id>/', views.student_profile, name='student_profile'),
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),

    path('', views.dashboard, name='dashboard'),
    # Admin dashboard split pages
    path('admin_overview/', views.admin_overview, name='admin_overview'),
    path('admin_teachers/', views.admin_teachers, name='admin_teachers'),
    path('admin_teachers/edit/<int:teacher_id>/', views.edit_teacher, name='edit_teacher'),
    path('admin_teachers/delete/<int:teacher_id>/', views.delete_teacher, name='delete_teacher'),
    path('admin_students/', views.admin_students, name='admin_students'),
    path('admin_classes/', views.admin_classes, name='admin_classes'),
    path('class_profile/<int:class_id>/', views.class_profile, name='class_profile'),
    path('edit_class/<int:class_id>/', views.edit_class, name='edit_class'),
    path('delete_class/<int:class_id>/', views.delete_class, name='delete_class'),
    path('admin_analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin_subjects/', views.admin_subjects, name='admin_subjects'),
    path('admin_academic_years/', views.admin_academic_years, name='admin_academic_years'),
    path('admin_exams/', views.admin_exams, name='admin_exams'),
    path('admin_events/', views.admin_events, name='admin_events'),
    path('teacher/upload_marksheet/', views.upload_marksheet, name='upload_marksheet'),
    # --- AJAX Modal Add Endpoints ---
    path('dashboard/students/add/', views.add_student_ajax, name='add_student_ajax'),
    path('dashboard/teachers/add/', views.add_teacher_ajax, name='add_teacher_ajax'),
    path('dashboard/classes/add/', views.add_class_ajax, name='add_class_ajax'),
    path('dashboard/subjects/add/', views.add_subject_ajax, name='add_subject_ajax'),
    # --- FullCalendar AJAX Event Endpoints ---
    path('dashboard/events/json/', views.events_json, name='events_json'),
    path('dashboard/events/create/', views.event_create, name='event_create'),
    path('dashboard/events/update/', views.event_update, name='event_update'),
    path('dashboard/events/delete/', views.event_delete, name='event_delete'),
    # --- FullCalendar AJAX Event Endpoints ---
    path('dashboard/events/feed/', views.events_feed, name='events_feed'),
    path('dashboard/events/create/', views.event_create, name='event_create'),
    path('dashboard/events/update/', views.event_update, name='event_update'),
    path('dashboard/events/delete/', views.event_delete, name='event_delete'),

]

