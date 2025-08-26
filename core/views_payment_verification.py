from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import FeePayment, Student, FeeAssignment, Term, MpesaTransaction, MpesaC2BLedger
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Sum as _Sum
from decimal import Decimal
from .mpesa_utils import query_stk_status

def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'admin'

@login_required
@user_passes_test(is_admin)
@require_POST
def verify_payment(request, payment_id):
    payment = get_object_or_404(FeePayment, id=payment_id)
    if payment.status != 'pending':
        return JsonResponse({'success': False, 'error': 'Payment already verified or rejected.'}, status=400)
    payment.status = 'approved'
    payment.save()
    return JsonResponse({'success': True, 'status': payment.get_status_display()})


@login_required
@require_POST
def verify_payment_by_reference(request):
    """Approve a pending FeePayment when the provided reference matches.

    Scope rules:
    - Students can only verify their own pending payments by reference.
    - Admins can verify any student's pending payment by reference.
    """
    reference = (request.POST.get('reference') or '').strip()
    if not reference:
        return JsonResponse({'success': False, 'error': 'Reference code is required.'}, status=400)

    # Resolve student if requester is a student
    student = None
    if getattr(request.user, 'role', None) == 'student':
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student profile not found.'}, status=400)

    # If reference looks like a CheckoutRequestID (ws_CO_{...}), handle STK Query first
    if reference.lower().startswith('ws_co_'):
        tx = MpesaTransaction.objects.filter(checkout_request_id=reference).first()
        if not tx:
            return JsonResponse({'success': False, 'error': 'No STK transaction found for that CheckoutRequestID.'}, status=404)

        # Scope: students can only verify their own tx
        if student is not None and tx.student_id and tx.student_id != student.id:
            return JsonResponse({'success': False, 'error': 'You can only verify your own transaction.'}, status=403)

        resp = query_stk_status(reference)
        if not resp or resp.get('error'):
            return JsonResponse({'success': False, 'error': f"STK query failed: {resp.get('error', 'Unknown error')}"}, status=502)
        result_code = str(resp.get('ResultCode', ''))
        result_desc = resp.get('ResultDesc') or ''
        if result_code == '0':
            # Treat as success even if receipt is missing; create/approve FeePayment
            tx.status = 'success'
            tx.result_code = 0
            tx.result_desc = result_desc
            tx.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])

            # Choose student
            resolved_student = tx.student or student
            if not resolved_student and tx.phone_number:
                resolved_student = Student.objects.filter(phone=tx.phone_number).first()
            if not resolved_student:
                return JsonResponse({'success': False, 'error': 'Transaction success but student not resolved. Contact admin.'}, status=400)

            # Determine current term and link a fee assignment if possible
            today = timezone.now().date()
            current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date').first()
            outstanding_assignment = None
            if current_term and resolved_student.class_group_id:
                fee_assignments = FeeAssignment.objects.filter(class_group=resolved_student.class_group, term=current_term)
                for fa in fee_assignments:
                    total_paid = FeePayment.objects.filter(student=resolved_student, fee_assignment=fa).aggregate(total=_Sum('amount_paid'))['total'] or 0
                    if float(total_paid) < float(fa.amount):
                        outstanding_assignment = fa
                        break
                if not outstanding_assignment and fee_assignments.exists():
                    outstanding_assignment = fee_assignments.first()

            # Avoid duplicates if payment already exists
            existing = FeePayment.objects.filter(reference__iexact=reference).first()
            if existing:
                if existing.status != 'approved':
                    existing.status = 'approved'
                    existing.save(update_fields=['status'])
                return JsonResponse({'success': True, 'payment_id': existing.id, 'status': existing.status, 'amount': str(existing.amount_paid), 'payment_date': existing.payment_date.strftime('%Y-%m-%d %H:%M:%S')})

            created_payment = FeePayment.objects.create(
                student=resolved_student,
                fee_assignment=outstanding_assignment,
                amount_paid=Decimal(str(tx.amount or 0)),
                payment_method='mpesa',
                reference=tx.mpesa_receipt or tx.checkout_request_id,
                phone_number=tx.phone_number,
                status='approved',
                mpesa_transaction=tx,
            )
            return JsonResponse({'success': True, 'payment_id': created_payment.id, 'status': created_payment.status, 'amount': str(created_payment.amount_paid), 'payment_date': created_payment.payment_date.strftime('%Y-%m-%d %H:%M:%S')})
        else:
            # Mark tx as failed for traceability
            tx.status = 'failed'
            try:
                tx.result_code = int(result_code)
            except Exception:
                tx.result_code = None
            tx.result_desc = result_desc
            tx.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])
            return JsonResponse({'success': False, 'error': f"STK status: {result_desc or 'Failed'}"}, status=400)

    qs = FeePayment.objects.filter(status='pending', reference__iexact=reference)
    if student is not None:
        qs = qs.filter(student=student)

    payment = qs.first()
    if not payment:
        # If payment already exists but not pending, approve it (idempotent recovery)
        existing_any = FeePayment.objects.filter(reference__iexact=reference)
        if student is not None:
            existing_any = existing_any.filter(student=student)
        existing_any = existing_any.first()
        if existing_any:
            if existing_any.status != 'approved':
                existing_any.status = 'approved'
                existing_any.save(update_fields=['status'])
            return JsonResponse({
                'success': True,
                'payment_id': existing_any.id,
                'status': existing_any.status,
                'amount': str(existing_any.amount_paid),
                'payment_date': existing_any.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
            })

        # Fallback 1: PayBill ledger (C2B) – callback may have saved a ledger entry
        ledger = MpesaC2BLedger.objects.filter(trans_id__iexact=reference).first()
        # Fallback 2: STK push transaction – callback may have failed, but we still have MpesaTransaction
        tx_only = None
        if not ledger:
            tx_only = MpesaTransaction.objects.filter(mpesa_receipt__iexact=reference).first()
            if not tx_only:
                return JsonResponse({'success': False, 'error': 'No payment found with that reference.'}, status=404)

        # Resolve student
        resolved_student = student
        if resolved_student is None:
            adm = None
            # Prefer explicit bill ref if we have a ledger; otherwise try tx account reference
            bill_ref = None
            msisdn = None
            if ledger:
                bill_ref = ledger.bill_ref
                msisdn = ledger.msisdn
            elif tx_only:
                bill_ref = getattr(tx_only, 'account_reference', None)
                msisdn = getattr(tx_only, 'phone_number', None)
            if bill_ref and isinstance(bill_ref, str) and bill_ref.startswith('Account#'):
                adm = bill_ref.split('#', 1)[1].strip()
            if adm:
                resolved_student = Student.objects.filter(admission_no=adm).first()
            if not resolved_student and msisdn:
                resolved_student = Student.objects.filter(phone=msisdn).first()

        if not resolved_student:
            return JsonResponse({'success': False, 'error': 'Payment found in ledger but student could not be resolved. Contact admin.'}, status=400)

        # Find current term and an outstanding assignment
        today = timezone.now().date()
        current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date').first()
        outstanding_assignment = None
        if current_term and resolved_student.class_group_id:
            fee_assignments = FeeAssignment.objects.filter(class_group=resolved_student.class_group, term=current_term)
            for fa in fee_assignments:
                total_paid = FeePayment.objects.filter(student=resolved_student, fee_assignment=fa).aggregate(total=_Sum('amount_paid'))['total'] or 0
                if float(total_paid) < float(fa.amount):
                    outstanding_assignment = fa
                    break
            if not outstanding_assignment and fee_assignments.exists():
                outstanding_assignment = fee_assignments.first()

        # Link MpesaTransaction if we have it
        tx = MpesaTransaction.objects.filter(mpesa_receipt__iexact=reference).first()
        if not tx and ledger and ledger.bill_ref:
            tx = MpesaTransaction.objects.filter(account_reference=ledger.bill_ref).order_by('-created_at').first()
        if not tx:
            tx = tx_only

        # Create approved FeePayment from ledger
        # Choose amount/reference/phone from ledger if present, else from tx_only
        amt = None
        ref_code = reference
        phone_val = None
        if ledger:
            amt = Decimal(str(ledger.amount or 0))
            ref_code = ledger.trans_id
            phone_val = ledger.msisdn
        elif tx_only:
            amt = Decimal(str(getattr(tx_only, 'amount', 0) or 0))
            ref_code = getattr(tx_only, 'mpesa_receipt', reference)
            phone_val = getattr(tx_only, 'phone_number', None)

        created_payment = FeePayment.objects.create(
            student=resolved_student,
            fee_assignment=outstanding_assignment,
            amount_paid=amt,
            payment_method='mpesa',
            reference=ref_code,
            phone_number=phone_val,
            status='approved',
            mpesa_transaction=tx,
        )

        return JsonResponse({
            'success': True,
            'payment_id': created_payment.id,
            'status': created_payment.status,
            'amount': str(created_payment.amount_paid),
            'payment_date': created_payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
        })

    payment.status = 'approved'
    payment.save(update_fields=['status'])

    return JsonResponse({
        'success': True,
        'payment_id': payment.id,
        'status': payment.status,
        'amount': str(payment.amount_paid),
        'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def reconcile_pending_stk(request):
    """Admin action: scan recent pending STK transactions, query status, and create/approve FeePayment on success."""
    # Optional: limit to last N minutes to keep it quick
    pending = MpesaTransaction.objects.filter(status='pending').order_by('-created_at')[:50]
    reconciled = []
    failed = []
    for tx in pending:
        resp = query_stk_status(tx.checkout_request_id)
        if not resp or resp.get('error'):
            failed.append({'checkout': tx.checkout_request_id, 'error': resp.get('error', 'query failed')})
            continue
        if str(resp.get('ResultCode', '')) == '0':
            tx.status = 'success'
            tx.result_code = 0
            tx.result_desc = resp.get('ResultDesc') or ''
            tx.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])

            # Create payment if none exists
            if not FeePayment.objects.filter(reference__in=[tx.mpesa_receipt or '', tx.checkout_request_id]).exists():
                resolved_student = tx.student
                if not resolved_student and tx.phone_number:
                    resolved_student = Student.objects.filter(phone=tx.phone_number).first()
                if not resolved_student:
                    failed.append({'checkout': tx.checkout_request_id, 'error': 'student not resolved'})
                    continue

                today = timezone.now().date()
                current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date').first()
                outstanding_assignment = None
                if current_term and resolved_student.class_group_id:
                    fee_assignments = FeeAssignment.objects.filter(class_group=resolved_student.class_group, term=current_term)
                    for fa in fee_assignments:
                        total_paid = FeePayment.objects.filter(student=resolved_student, fee_assignment=fa).aggregate(total=_Sum('amount_paid'))['total'] or 0
                        if float(total_paid) < float(fa.amount):
                            outstanding_assignment = fa
                            break
                    if not outstanding_assignment and fee_assignments.exists():
                        outstanding_assignment = fee_assignments.first()

                FeePayment.objects.create(
                    student=resolved_student,
                    fee_assignment=outstanding_assignment,
                    amount_paid=Decimal(str(tx.amount or 0)),
                    payment_method='mpesa',
                    reference=tx.mpesa_receipt or tx.checkout_request_id,
                    phone_number=tx.phone_number,
                    status='approved',
                    mpesa_transaction=tx,
                )
            reconciled.append({'checkout': tx.checkout_request_id})
        else:
            tx.status = 'failed'
            try:
                tx.result_code = int(resp.get('ResultCode'))
            except Exception:
                tx.result_code = None
            tx.result_desc = resp.get('ResultDesc') or ''
            tx.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])
            failed.append({'checkout': tx.checkout_request_id, 'error': tx.result_desc})

    return JsonResponse({'success': True, 'reconciled': reconciled, 'failed': failed})
