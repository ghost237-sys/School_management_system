from django.urls import path
from . import views

urlpatterns = [
    path('', views.timetable_view, name='timetable_view'),
    path('edit/', views.timetable_edit_api, name='timetable_edit_api'),
    # path('api/', views.timetable_api, name='timetable_api'),
    # path('api/add/', views.add_slot_api, name='add_slot_api'),
    # path('api/edit/<int:slot_id>/', views.edit_slot_api, name='edit_slot_api'),
    # path('api/delete/<int:slot_id>/', views.delete_slot_api, name='delete_slot_api'),
    # path('api/slot/<int:slot_id>/', views.get_slot_api, name='get_slot_api'),
    # path('export/pdf/', views.timetable_pdf_export, name='timetable_pdf_export'),
    path('notifications/', views.get_notifications_api, name='get_notifications_api'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_as_read_api, name='mark_notification_as_read_api'),
]
