from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('teacher_dashboard/<int:teacher_id>/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher_profile/<int:teacher_id>/', views.teacher_profile, name='teacher_profile'),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
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
]

