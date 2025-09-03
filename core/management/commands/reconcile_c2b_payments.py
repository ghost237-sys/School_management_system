from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from typing import Optional
import re

from core.models import (
    MpesaC2BLedger,
    MpesaTransaction,
    FeePayment,
    Student,
    Term,
    FeeAssignment,
)


class Command(BaseCommand):
    help = (
        "Reconcile PayBill (C2B) ledger entries into FeePayment records.\n"
        "Idempotent: skips entries already posted (by checking FeePayment.reference == TransID).\n"
        "Attempts to match student via BillRef formats like '400200#<ADM>', 'Account#<ADM>', plain '<ADM>', or 'ADM<digits>'.\n"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="ISO date (YYYY-MM-DD) to only process ledger entries created on/after this date.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not persist any changes; only show what would be done.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max number of ledger rows to scan (default 500).",
        )

    def handle(self, *args, **options):
        since = options.get("since")
        dry_run = options.get("dry_run", False)
        limit = int(options.get("limit") or 500)

        qs = MpesaC2BLedger.objects.all().order_by("-created_at")
        if since:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(since)
                qs = qs.filter(created_at__date__gte=dt.date())
            except Exception:
                self.stdout.write(self.style.WARNING(f"Ignoring invalid --since value: {since}"))
        qs = qs[:limit]

        processed = 0
        created = 0
        skipped_existing = 0
        unmatched = 0

        for led in qs:
            processed += 1
            trans_id = (led.trans_id or '').strip()
            bill_ref = (led.bill_ref or '').strip()
            msisdn = (led.msisdn or '').strip()

            if not trans_id:
                continue

            # Idempotency: skip if FeePayment already exists for this TransID
            if FeePayment.objects.filter(reference=trans_id).exists():
                skipped_existing += 1
                continue

            student = self._resolve_student(bill_ref, msisdn)
            if not student:
                # Track unmatched, but proceed to create an unassigned FeePayment
                # to mirror live auto-reconciliation behavior in c2b_confirmation
                unmatched += 1

            # Determine current term and outstanding assignment (best-effort)
            today = timezone.now().date()
            current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date').first()
            outstanding_assignment: Optional[FeeAssignment] = None
            if student and current_term and student.class_group:
                fee_assignments = FeeAssignment.objects.filter(class_group=student.class_group, term=current_term)
                from django.db.models import Sum as _Sum
                for fa in fee_assignments:
                    total_paid = FeePayment.objects.filter(student=student, fee_assignment=fa).aggregate(total=_Sum('amount_paid'))['total'] or 0
                    if float(total_paid) < float(fa.amount):
                        outstanding_assignment = fa
                        break
                if not outstanding_assignment and fee_assignments.exists():
                    outstanding_assignment = fee_assignments.first()

            # Ensure MpesaTransaction row exists/updated
            tx = MpesaTransaction.objects.filter(mpesa_receipt=trans_id).first()
            if not tx:
                tx = MpesaTransaction(
                    student=student,
                    phone_number=msisdn or '',
                    amount=led.amount or Decimal('0'),
                    account_reference=bill_ref or '',
                    checkout_request_id=f"c2b-{trans_id}",
                    status='success',
                    mpesa_receipt=trans_id,
                    result_desc='C2B Reconciled',
                )
                if not dry_run:
                    tx.save()

            # Create approved FeePayment
            if not dry_run:
                FeePayment.objects.create(
                    student=student,
                    fee_assignment=outstanding_assignment,
                    amount_paid=led.amount or Decimal('0'),
                    payment_method='Mpesa Paybill',
                    reference=trans_id,
                    phone_number=msisdn or '',
                    status='approved',
                    mpesa_transaction=tx,
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Reconciliation done. scanned={processed} created={created} skipped_existing={skipped_existing} unmatched={unmatched}"
        ))

    def _resolve_student(self, bill_ref: str, msisdn: str) -> Optional[Student]:
        """Resolve a student from BillRef or phone.
        Supports formats like '400200#123456', 'Account#123456', 'ADM123456', or plain '123456'.
        """
        # 1) Try BillRef
        if bill_ref:
            ref = bill_ref.strip()
            adm = None
            if '#' in ref:
                adm = ref.split('#')[-1].strip()
            elif ref.lower().startswith('account#'):
                adm = ref.split('#', 1)[1].strip()
            else:
                adm = re.sub(r"[^A-Za-z0-9]", "", ref)
            if adm:
                # Try multiple common variants to maximize matching rate
                candidates = []
                base = adm
                # Normalize base parts
                if base.lower().startswith('adm'):
                    base = base[3:]
                base_no_s = base.lstrip('S').lstrip('s')
                # Build candidate list
                candidates.append(adm)
                candidates.append(base)
                candidates.append(base_no_s)
                candidates.append(('S' + base_no_s))
                candidates.append(('S' + base_no_s.zfill(5)))
                candidates.append(base_no_s.zfill(5))
                # Deduplicate while preserving order
                seen = set()
                unique_candidates = []
                for c in candidates:
                    c_norm = c.strip()
                    if c_norm and c_norm not in seen:
                        seen.add(c_norm)
                        unique_candidates.append(c_norm)
                for cand in unique_candidates:
                    student = Student.objects.filter(admission_no__iexact=cand).first()
                    if student:
                        return student
        # 2) Fallback by phone
        phone = self._normalize_msisdn(msisdn)
        if phone:
            student = Student.objects.filter(phone=phone).first()
            if student:
                return student
        return None

    def _normalize_msisdn(self, phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        p = str(phone).strip()
        if p.startswith('+'):
            p = p[1:]
        if p.startswith('0'):
            return '254' + p[1:]
        if p.startswith('7') and len(p) == 9:
            return '254' + p
        return p if p.startswith('254') else None
