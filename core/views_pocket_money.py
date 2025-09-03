from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal

from .models import PocketMoney, Student, User
from .forms import PocketMoneyForm, PocketMoneyFilterForm


def is_admin_or_clerk(user):
    """Check if user is admin or clerk (finance officer)."""
    return user.is_authenticated and getattr(user, 'role', None) in ('admin', 'clerk')


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_list(request):
    """List all pocket money transactions with filtering and pagination."""
    transactions = PocketMoney.objects.select_related('student__user', 'student__class_group', 'processed_by').order_by('-transaction_date')
    
    # Apply filters
    filter_form = PocketMoneyFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['student']:
            transactions = transactions.filter(student=filter_form.cleaned_data['student'])
        
        if filter_form.cleaned_data['transaction_type']:
            transactions = transactions.filter(transaction_type=filter_form.cleaned_data['transaction_type'])
        
        if filter_form.cleaned_data['status']:
            transactions = transactions.filter(status=filter_form.cleaned_data['status'])
        
        if filter_form.cleaned_data['date_from']:
            transactions = transactions.filter(transaction_date__date__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data['date_to']:
            transactions = transactions.filter(transaction_date__date__lte=filter_form.cleaned_data['date_to'])
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        transactions = transactions.filter(
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__admission_no__icontains=search_query) |
            Q(reference__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(transactions, 25)  # Show 25 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary statistics
    total_deposits = transactions.filter(transaction_type='deposit', status='approved').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    total_withdrawals = transactions.filter(transaction_type='withdrawal', status='approved').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    net_balance = total_deposits - total_withdrawals
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'search_query': search_query,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'net_balance': net_balance,
        'total_transactions': transactions.count(),
    }
    
    return render(request, 'finance/pocket_money_list.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_add(request):
    """Add a new pocket money transaction."""
    if request.method == 'POST':
        form = PocketMoneyForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.processed_by = request.user
            transaction.save()
            
            messages.success(request, f'Pocket money {transaction.get_transaction_type_display().lower()} of KES {transaction.amount} for {transaction.student} has been recorded successfully.')
            return redirect('pocket_money_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill the student when coming from a personalized window: ?student=<id>
        student_id = request.GET.get('student')
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                form = PocketMoneyForm(initial={'student': student.id})
            except Student.DoesNotExist:
                form = PocketMoneyForm()
                messages.warning(request, 'The specified student was not found. Please select a student.')
        else:
            form = PocketMoneyForm()
    
    return render(request, 'finance/pocket_money_form.html', {
        'form': form,
        'title': 'Add Pocket Money Transaction',
        'action': 'Add'
    })


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_edit(request, transaction_id):
    """Edit an existing pocket money transaction."""
    transaction = get_object_or_404(PocketMoney, id=transaction_id)
    
    if request.method == 'POST':
        form = PocketMoneyForm(request.POST, instance=transaction)
        if form.is_valid():
            updated_transaction = form.save(commit=False)
            updated_transaction.processed_by = request.user  # Update processed_by to current user
            updated_transaction.save()
            
            messages.success(request, f'Pocket money transaction for {updated_transaction.student} has been updated successfully.')
            return redirect('pocket_money_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PocketMoneyForm(instance=transaction)
    
    return render(request, 'finance/pocket_money_form.html', {
        'form': form,
        'title': 'Edit Pocket Money Transaction',
        'action': 'Update',
        'transaction': transaction
    })


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_delete(request, transaction_id):
    """Delete a pocket money transaction."""
    transaction = get_object_or_404(PocketMoney, id=transaction_id)
    
    if request.method == 'POST':
        student_name = str(transaction.student)
        transaction.delete()
        messages.success(request, f'Pocket money transaction for {student_name} has been deleted successfully.')
        return redirect('pocket_money_list')
    
    return render(request, 'finance/pocket_money_confirm_delete.html', {
        'transaction': transaction
    })


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def student_pocket_money_balance(request, student_id):
    """Get pocket money balance for a specific student (AJAX endpoint)."""
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Calculate balance
        deposits = PocketMoney.objects.filter(
            student=student, 
            transaction_type='deposit', 
            status='approved'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        withdrawals = PocketMoney.objects.filter(
            student=student, 
            transaction_type='withdrawal', 
            status='approved'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        adjustments = PocketMoney.objects.filter(
            student=student, 
            transaction_type='adjustment', 
            status='approved'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        balance = deposits - withdrawals + adjustments
        
        # Get recent transactions
        recent_transactions = PocketMoney.objects.filter(
            student=student
        ).order_by('-transaction_date')[:5]
        
        transactions_data = []
        for trans in recent_transactions:
            transactions_data.append({
                'date': trans.transaction_date.strftime('%Y-%m-%d %H:%M'),
                'type': trans.get_transaction_type_display(),
                'amount': float(trans.amount),
                'signed_amount': float(trans.signed_amount),
                'status': trans.get_status_display(),
                'description': trans.description or '',
                'reference': trans.reference or ''
            })
        
        return JsonResponse({
            'success': True,
            'student_name': student.full_name,
            'admission_no': student.admission_no,
            'class_group': str(student.class_group) if student.class_group else 'N/A',
            'balance': float(balance),
            'deposits': float(deposits),
            'withdrawals': float(withdrawals),
            'adjustments': float(adjustments),
            'recent_transactions': transactions_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def search_students_ajax(request):
    """AJAX endpoint for auto-searching students by name or admission number."""
    query = request.GET.get('q', '').strip()
    
    print(f"Search query: '{query}'")  # Debug log
    
    if len(query) < 2:
        return JsonResponse({'students': []})
    
    # Search by admission number or name (case-insensitive)
    # Optimize: select only required fields and avoid per-student balance computation here
    students_qs = (
        Student.objects
        .select_related('user', 'class_group')
        .only('id', 'admission_no', 'class_group__name', 'user__first_name', 'user__last_name')
        .filter(
            Q(admission_no__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query)
        )
        .exclude(user__isnull=True)
        .order_by('user__first_name', 'user__last_name')[:10]  # Limit to 10 results for snappier UX
    )

    students_list = list(students_qs)
    print(f"Found {len(students_list)} students")  # Debug log

    # If no students found, print a small sample for debugging
    if not students_list:
        sample = list(Student.objects.select_related('user').exclude(user__isnull=True)[:3])
        print(f"Sample students in database: {len(sample)}")
        for s in sample:
            print(f"- {getattr(s.user, 'first_name', '')} {getattr(s.user, 'last_name', '')} ({s.admission_no})")

    students_data = []
    for student in students_list:
        students_data.append({
            'id': student.id,
            'name': student.full_name,
            'admission_no': student.admission_no,
            'class_group': str(student.class_group) if student.class_group else 'N/A',
            # Do not include balance here; fetch via student_pocket_money_balance after selection
            'display_text': f"{student.full_name} - {student.admission_no} ({student.class_group or 'N/A'})"
        })

    return JsonResponse({'students': students_data})


@login_required(login_url='login')
@user_passes_test(is_admin_or_clerk)
def pocket_money_student_summary(request, student_id):
    """Detailed pocket money summary for a specific student."""
    student = get_object_or_404(Student, id=student_id)
    
    # Get all transactions for this student
    transactions = PocketMoney.objects.filter(student=student).order_by('-transaction_date')
    
    # Calculate balances
    deposits = transactions.filter(transaction_type='deposit', status='approved').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    withdrawals = transactions.filter(transaction_type='withdrawal', status='approved').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    adjustments = transactions.filter(transaction_type='adjustment', status='approved').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    
    current_balance = deposits - withdrawals + adjustments
    
    # Pagination for transactions
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'student': student,
        'page_obj': page_obj,
        'current_balance': current_balance,
        'total_deposits': deposits,
        'total_withdrawals': withdrawals,
        'total_adjustments': adjustments,
        'total_transactions': transactions.count(),
    }
    
    return render(request, 'finance/student_pocket_money_summary.html', context)
