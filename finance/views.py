from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
import calendar
from .models import FinanceTransaction
from home.models import GymBranch
from decimal import Decimal
from datetime import datetime

@login_required
def finance_dashboard(request):
    user = request.user
    
    if not user.gym:
        messages.error(request, "Account not associated with any gym.")
        return redirect('user-dashboard')

    context = {
        'gym': user.gym,
        'role': user.role,
    }

    # Date filtering logic
    today = timezone.now().date()
    default_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    default_end = today.replace(day=last_day)
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else default_end
    except ValueError:
        start_date = default_start
        end_date = default_end
        
    context['start_date'] = start_date.strftime('%Y-%m-%d')
    context['end_date'] = end_date.strftime('%Y-%m-%d')

    # Base queryset
    transactions = FinanceTransaction.objects.filter(is_deleted=False, date__gte=start_date, date__lte=end_date)
    
    if user.role == 'gym_admin':
        transactions = transactions.filter(gym=user.gym)
        context['branches'] = user.gym.gym_branches.filter(is_active=True, is_deleted=False)
        
        # Optional branch filter for UI
        filter_branch_id = request.GET.get('branch_id')
        if filter_branch_id:
            transactions = transactions.filter(branch_id=filter_branch_id)
            context['filter_branch_id'] = int(filter_branch_id)
        
        total_income = transactions.filter(transaction_type='Income').aggregate(sum=Sum('amount'))['sum'] or Decimal('0')
        total_expense = transactions.filter(transaction_type='Expense').aggregate(sum=Sum('amount'))['sum'] or Decimal('0')
        balance = total_income - total_expense
        
        context['total_income'] = total_income
        context['total_expense'] = total_expense
        context['balance'] = balance
        
    elif user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
        transactions = transactions.filter(branch=user.branch, transaction_type='Expense')
        context['branch'] = user.branch
        
        total_expense = transactions.aggregate(sum=Sum('amount'))['sum'] or Decimal('0')
        context['total_expense'] = total_expense
    else:
        transactions = transactions.none()

    context['transactions'] = transactions.order_by('-date', '-created_at')
    
    return render(request, "user/finance/dashboard.html", context)


@login_required
def add_transaction(request):
    user = request.user
    
    if not user.gym:
        messages.error(request, "Account not associated with any gym.")
        return redirect('user-dashboard')
        
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        if transaction_type not in ['Income', 'Expense']:
            messages.error(request, "Invalid transaction type.")
            return redirect('finance-dashboard')
            
        # Permission check: Only gym_admin can add Income
        if transaction_type == 'Income' and user.role != 'gym_admin':
            messages.error(request, "Only Gym Admin can record Income manually.")
            return redirect('finance-dashboard')
            
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        description = request.POST.get('description')
        category = request.POST.get('category') or 'General'
        receipt_number = request.POST.get('receipt_number') or ''
        branch_id = request.POST.get('branch_id')
        
        branch = None
        if user.role == 'gym_admin' and branch_id:
            try:
                branch = GymBranch.objects.get(id=branch_id, gym=user.gym)
            except GymBranch.DoesNotExist:
                pass
        elif user.role in ['branch_admin', 'staff', 'trainer']:
            branch = user.branch

        if not date:
            from django.utils import timezone
            date = timezone.now().date()
            
        if not amount:
            messages.error(request, "Amount is required.")
            return redirect('finance-dashboard')
            
        try:
            FinanceTransaction.objects.create(
                gym=user.gym,
                branch=branch,
                transaction_type=transaction_type,
                amount=amount,
                date=date,
                description=description,
                category=category,
                receipt_number=receipt_number,
                recorded_by=user
            )
            messages.success(request, f"{transaction_type} recorded successfully.")
        except Exception as e:
            messages.error(request, f"Error adding transaction: {str(e)}")
            
    return redirect('finance-dashboard')
