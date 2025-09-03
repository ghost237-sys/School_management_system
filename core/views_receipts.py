from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Sum, Q

from .models import FeePayment, PocketMoney, FeeAssignment, Term
from landing.models import SiteSettings


def is_admin_or_clerk(user):
    return user.is_authenticated and getattr(user, 'role', None) in ('admin', 'clerk')


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def fee_payment_receipt(request, payment_id: int):
    payment = get_object_or_404(
        FeePayment.objects.select_related(
            'student__user', 'fee_assignment__fee_category', 'mpesa_transaction'
        ),
        id=payment_id,
    )
    student = payment.student
    # Determine the relevant term: prefer the payment's assignment term; else, term containing payment date
    relevant_term = None
    if payment.fee_assignment_id and payment.fee_assignment and payment.fee_assignment.term_id:
        relevant_term = payment.fee_assignment.term
    if not relevant_term:
        pay_date = payment.payment_date.date() if payment.payment_date else timezone.now().date()
        relevant_term = Term.objects.filter(start_date__lte=pay_date, end_date__gte=pay_date).order_by('start_date').first()

    # Fetch all fee assignments for the student's class in that term
    assignments = FeeAssignment.objects.select_related('fee_category', 'class_group', 'term').filter(
        class_group=student.class_group,
        term=relevant_term
    )

    rows = []
    assigned_total = 0
    paid_total_after = 0
    balance_total = 0

    for fa in assignments:
        # Sum approved payments BEFORE this payment timestamp for this assignment
        paid_before = (
            FeePayment.objects.filter(
                student=student,
                fee_assignment=fa,
                status='approved',
                payment_date__lt=payment.payment_date,
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
        )
        # Allocation of this payment to this assignment
        this_alloc = payment.amount_paid if payment.fee_assignment_id == fa.id else 0
        paid_after = paid_before + this_alloc
        assigned_total += float(fa.amount)
        paid_total_after += float(paid_after)
        balance = float(fa.amount) - float(paid_after)
        balance_total += balance
        rows.append({
            'category': fa.fee_category.name if fa.fee_category else '—',
            'assigned': fa.amount,
            'paid_before': paid_before,
            'this_payment': this_alloc,
            'paid_after': paid_after,
            'balance': balance,
        })

    settings = SiteSettings.objects.first()
    context = {
        'payment': payment,
        'site_settings': settings,
        'generated_at': timezone.now(),
        'assignment_rows': rows,
        'assigned_total': assigned_total,
        'paid_total_after': paid_total_after,
        'balance_total': balance_total,
        'relevant_term': relevant_term,
    }
    template_name = 'receipts/fee_payment_receipt.html'
    if request.GET.get('print') == '1':
        template_name = 'receipts/fee_payment_receipt_print.html'
    return render(request, template_name, context)


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_receipt(request, transaction_id: int):
    txn = get_object_or_404(
        PocketMoney.objects.select_related('student__user', 'student__class_group', 'processed_by'),
        id=transaction_id,
    )
    settings = SiteSettings.objects.first()
    context = {
        'transaction': txn,
        'site_settings': settings,
        'generated_at': timezone.now(),
    }
    template_name = 'receipts/pocket_money_receipt.html'
    if request.GET.get('print') == '1':
        template_name = 'receipts/pocket_money_receipt_print.html'
    return render(request, template_name, context)
