from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    path('widget/', views.widget, name='widget'),
    path('history/', views.history, name='history'),
    path('message/', views.message, name='message'),
    path('clear/', views.clear_history, name='clear'),
]
