from django.urls import path
from .views_payment_verification import verify_payment, verify_payment_by_reference

urlpatterns = [
    path('verify_payment/<int:payment_id>/', verify_payment, name='verify_payment'),
    path('verify_payment/by-reference/', verify_payment_by_reference, name='verify_payment_by_reference'),
]
