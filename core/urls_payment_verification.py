from django.urls import path
from .views_payment_verification import verify_payment, verify_payment_by_reference, reconcile_pending_stk

urlpatterns = [
    path('verify_payment/<int:payment_id>/', verify_payment, name='verify_payment'),
    path('verify_payment/by-reference/', verify_payment_by_reference, name='verify_payment_by_reference'),
    path('verify_payment/reconcile-pending-stk/', reconcile_pending_stk, name='reconcile_pending_stk'),
]
