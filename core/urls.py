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
    path('register/', views.register_view, name='register'),
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
    path('admin_exams/', views.admin_exams, name='admin_exams'),
    path('teacher/upload_marksheet/', views.upload_marksheet, name='upload_marksheet'),
]

