from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import json

from .models import (
    MpesaC2BLedger,
    MpesaTransaction,
    FeePayment,
    Student,
    Term,
    FeeAssignment,
    OptionalOffer,
    StudentOptionalCharge,
    OptionalChargePayment,
)


@csrf_exempt
@require_POST
def c2b_confirmation(request):
    """
    Safaricom Daraja C2B Confirmation endpoint.

    Expects JSON payload and stores essential fields:
    - TransID, TransTime, TransAmount, MSISDN, BillRefNumber
    Also stores additional metadata if present and the raw payload for auditing.

    Returns the acknowledgement object required by Daraja:
    {"ResultCode": 0, "ResultDesc": "Confirmation received successfully"}
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    # Extract standard fields (case-sensitive per Daraja docs)
    trans_id = (payload.get('TransID') or '').strip()
    trans_time = (payload.get('TransTime') or '').strip()
    trans_amount = payload.get('TransAmount')
    msisdn = (payload.get('MSISDN') or '').strip()
    bill_ref = (payload.get('BillRefNumber') or '').strip()

    # Optional metadata commonly present in C2B callbacks
    business_short_code = (payload.get('BusinessShortCode') or payload.get('ShortCode') or '').strip()
    third_party_trans_id = (payload.get('ThirdPartyTransID') or '').strip()
    first_name = (payload.get('FirstName') or '').strip()
    middle_name = (payload.get('MiddleName') or '').strip()
    last_name = (payload.get('LastName') or '').strip()
    org_account_balance = (payload.get('OrgAccountBalance') or '').strip()

    if not trans_id:
        return HttpResponseBadRequest('Missing TransID')

    # Persist to ledger (idempotent by unique trans_id)
    obj, created = MpesaC2BLedger.objects.get_or_create(
        trans_id=trans_id,
        defaults={
            'trans_time': trans_time or None,
            'amount': trans_amount or None,
            'msisdn': msisdn or None,
            'bill_ref': bill_ref or None,
            'business_short_code': business_short_code or None,
            'third_party_trans_id': third_party_trans_id or None,
            'first_name': first_name or None,
            'middle_name': middle_name or None,
            'last_name': last_name or None,
            'org_account_balance': org_account_balance or None,
            'raw': payload,
        }
    )
    if not created:
        # If it already exists, update select fields for completeness
        update_fields = []
        if trans_time and obj.trans_time != trans_time:
            obj.trans_time = trans_time
            update_fields.append('trans_time')
        if trans_amount is not None and obj.amount != trans_amount:
            obj.amount = trans_amount
            update_fields.append('amount')
        if msisdn and obj.msisdn != msisdn:
            obj.msisdn = msisdn
            update_fields.append('msisdn')
        if bill_ref and obj.bill_ref != bill_ref:
            obj.bill_ref = bill_ref
            update_fields.append('bill_ref')
        if business_short_code and obj.business_short_code != business_short_code:
            obj.business_short_code = business_short_code
            update_fields.append('business_short_code')
        if third_party_trans_id and obj.third_party_trans_id != third_party_trans_id:
            obj.third_party_trans_id = third_party_trans_id
            update_fields.append('third_party_trans_id')
        if first_name and obj.first_name != first_name:
            obj.first_name = first_name
            update_fields.append('first_name')
        if middle_name and obj.middle_name != middle_name:
            obj.middle_name = middle_name
            update_fields.append('middle_name')
        if last_name and obj.last_name != last_name:
            obj.last_name = last_name
            update_fields.append('last_name')
        if org_account_balance and obj.org_account_balance != org_account_balance:
            obj.org_account_balance = org_account_balance
            update_fields.append('org_account_balance')
        if payload and obj.raw != payload:
            obj.raw = payload
            update_fields.append('raw')
        if update_fields:
            obj.save(update_fields=update_fields)

    # Attempt auto-reconciliation (idempotent)
    try:
        # First, check if this is an Optional Charge payment via BillRef prefix: OC-<ADMNO>-<OFFERID>
        def _parse_optional_billref(ref: str):
            if not ref:
                return None, None
            r = ref.strip()
            if not r.upper().startswith('OC-'):
                return None, None
            # Accept formats: OC-ADM123-45 or OC-12345-45; extract admission_no token and offer id
            try:
                parts = r.split('-', 2)
                if len(parts) < 3:
                    return None, None
                adm_part = parts[1].strip()
                offer_id_part = parts[2].strip()
                # Normalize admission: remove spaces
                import re as _re
                adm_norm = _re.sub(r"[^A-Za-z0-9]", "", adm_part)
                offer_id = int(''.join(ch for ch in offer_id_part if ch.isdigit()))
                return adm_norm, offer_id
            except Exception:
                return None, None

        oc_adm, oc_offer_id = _parse_optional_billref(bill_ref)
        if oc_adm and oc_offer_id and trans_id:
            # Resolve student by admission number variants
            student = None
            base = oc_adm
            if base.lower().startswith('adm'):
                base = base[3:]
            base_no_s = base.lstrip('S').lstrip('s')
            candidates = [oc_adm, base, base_no_s, 'S' + base_no_s, 'S' + base_no_s.zfill(5), base_no_s.zfill(5)]
            seen = set()
            for cand in candidates:
                c = cand.strip()
                if c and c not in seen:
                    seen.add(c)
                    student = Student.objects.filter(admission_no__iexact=c).first()
                    if student:
                        break

            offer = OptionalOffer.objects.filter(pk=oc_offer_id, is_active=True).first()
            if student and offer:
                # Only process payments for already-enrolled students; do NOT auto-enroll here
                enrollment = StudentOptionalCharge.objects.filter(offer=offer, student=student).first()
                if not enrollment:
                    # Not enrolled; acknowledge without posting to optional charges or fees
                    return JsonResponse({
                        "ResultCode": 0,
                        "ResultDesc": "Confirmation received successfully"
                    })

                # Create MpesaTransaction record if missing
                tx = MpesaTransaction.objects.filter(mpesa_receipt=trans_id).first()
                if not tx:
                    tx = MpesaTransaction(
                        student=student,
                        phone_number=msisdn or '',
                        amount=trans_amount or 0,
                        account_reference=bill_ref or '',
                        checkout_request_id=f"c2b-{trans_id}",
                        status='success',
                        mpesa_receipt=trans_id,
                        result_desc='C2B OptionalCharge',
                    )
                    tx.save()

                # Idempotency: avoid duplicate OptionalChargePayment by reference
                if not OptionalChargePayment.objects.filter(reference=trans_id).exists():
                    OptionalChargePayment.objects.create(
                        student_optional_charge=enrollment,
                        amount_paid=trans_amount or 0,
                        method='Mpesa Paybill',
                        reference=trans_id,
                        phone_number=msisdn or '',
                        mpesa_transaction=tx,
                    )

                # Simple status update: mark enrollment paid if total payments >= amount
                from django.db.models import Sum as _Sum
                paid_total = enrollment.payments.aggregate(total=_Sum('amount_paid'))['total'] or 0
                if float(paid_total) >= float(enrollment.amount):
                    if enrollment.status != 'paid':
                        enrollment.status = 'paid'
                        enrollment.save(update_fields=['status', 'updated_at'])

                # We've handled as optional charge; return ACK now to avoid double-posting to fees
                return JsonResponse({
                    "ResultCode": 0,
                    "ResultDesc": "Confirmation received successfully"
                })

        # Skip if we already created a FeePayment for this TransID
        if trans_id and not FeePayment.objects.filter(reference=trans_id).exists():
            # Helper: extract an admission number from BillRef variants
            def _extract_adm(ref: str) -> str:
                if not ref:
                    return ''
                r = ref.strip()
                if '#' in r:
                    return r.split('#')[-1].strip()
                if r.lower().startswith('account#'):
                    return r.split('#', 1)[1].strip()
                import re as _re
                return _re.sub(r"[^A-Za-z0-9]", "", r)

            # Helper: normalize phone to 2547XXXXXXXX
            def _normalize_msisdn(p: str) -> str:
                if not p:
                    return ''
                s = str(p).strip()
                if s.startswith('+'):
                    s = s[1:]
                if s.startswith('0'):
                    return '254' + s[1:]
                if s.startswith('7') and len(s) == 9:
                    return '254' + s
                return s if s.startswith('254') else ''

            # Resolve student by BillRef first, then by phone
            adm = _extract_adm(bill_ref)
            student = None
            if adm:
                # Try a few common admission variants
                base = adm
                if base.lower().startswith('adm'):
                    base = base[3:]
                base_no_s = base.lstrip('S').lstrip('s')
                candidates = [adm, base, base_no_s, 'S' + base_no_s, 'S' + base_no_s.zfill(5), base_no_s.zfill(5)]
                seen = set()
                for cand in candidates:
                    c = cand.strip()
                    if c and c not in seen:
                        seen.add(c)
                        student = Student.objects.filter(admission_no__iexact=c).first()
                        if student:
                            break
            if not student:
                phone_norm = _normalize_msisdn(msisdn)
                if phone_norm:
                    student = Student.objects.filter(phone=phone_norm).first()

            # Determine current term and best fee assignment if we have a student
            from django.db.models import Sum as _Sum
            today = timezone.now().date()
            current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date').first()
            outstanding_assignment = None
            if student and current_term and student.class_group:
                fee_assignments = FeeAssignment.objects.filter(class_group=student.class_group, term=current_term)
                for fa in fee_assignments:
                    total_paid = FeePayment.objects.filter(student=student, fee_assignment=fa).aggregate(total=_Sum('amount_paid'))['total'] or 0
                    if float(total_paid) < float(fa.amount):
                        outstanding_assignment = fa
                        break
                if not outstanding_assignment and fee_assignments.exists():
                    outstanding_assignment = fee_assignments.first()

            # Ensure we have a MpesaTransaction row (student may be None)
            tx = MpesaTransaction.objects.filter(mpesa_receipt=trans_id).first()
            if not tx:
                tx = MpesaTransaction(
                    student=student,
                    phone_number=msisdn or '',
                    amount=trans_amount or 0,
                    account_reference=bill_ref or '',
                    checkout_request_id=f"c2b-{trans_id}",
                    status='success',
                    mpesa_receipt=trans_id,
                    result_desc='C2B Auto-Reconciled',
                )
                tx.save()

            # Create approved FeePayment even if student is None (unassigned)
            FeePayment.objects.create(
                student=student,
                fee_assignment=outstanding_assignment,
                amount_paid=trans_amount or 0,
                payment_method='Mpesa Paybill',
                reference=trans_id,
                phone_number=msisdn or '',
                status='approved',
                mpesa_transaction=tx,
            )
    except Exception:
        # Silent fail for auto-post to avoid breaking Daraja ACK; admins can reconcile later
        pass

    # Acknowledge receipt
    return JsonResponse({
        "ResultCode": 0,
        "ResultDesc": "Confirmation received successfully"
    })


@csrf_exempt
@require_POST
def c2b_validation(request):
    """
    Optional Safaricom Daraja C2B Validation endpoint.
    Returning ResultCode 0 accepts the transaction; non-zero rejects.
    For now, we accept all and optionally log for audit.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    # You can add custom checks here (e.g., allowed shortcode, bill ref format)
    # Accept by default to avoid blocking payments
    return JsonResponse({
        "ResultCode": 0,
        "ResultDesc": "Validation accepted",
    })
