from django.urls import path
from .views_payment_verification import verify_payment

urlpatterns = [
    path('verify_payment/<int:payment_id>/', verify_payment, name='verify_payment'),
]
