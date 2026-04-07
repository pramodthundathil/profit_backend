from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Payment
from .forms import PaymentForm, PaymentFilterForm
from members.models import Member, Subscription, SubscriptionInstallment

@login_required
def payment_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "No gym associated with your account.")
        return redirect('user-dashboard')

    # Defaults for form if no GET params
    initial_data = {}
    is_filtered = bool(request.GET)
    
    if not request.GET.get('start_date') and not request.GET.get('search'):
        today = timezone.now().date()
        initial_data['start_date'] = today.replace(day=1)
        initial_data['end_date'] = today

    # Initial Filter Form
    form = PaymentFilterForm(request.GET if is_filtered else None, initial=initial_data, user=user)
    
    # Base QuerySet
    payments = Payment.objects.filter(member__gym=user.gym).select_related('member', 'subscription')
    
    # Role-based restriction
    if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
        payments = payments.filter(member__branch=user.branch)
    
    # Apply Filters from Form
    if form.is_valid():
        search = form.cleaned_data.get('search')
        branch_id = form.cleaned_data.get('branch')
        status = form.cleaned_data.get('status')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        
        if search:
            payments = payments.filter(
                Q(member__first_name__icontains=search) | 
                Q(member__last_name__icontains=search) |
                Q(member__member_id__icontains=search) |
                Q(receipt_number__icontains=search)
            )
        
        if branch_id:
            payments = payments.filter(member__branch_id=branch_id)
            
        if status:
            payments = payments.filter(status=status)
            
        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
            
        if end_date:
            payments = payments.filter(payment_date__lte=end_date)
    else:
        # Initial Form Fallback Logic
        if not is_filtered:
            today = timezone.now().date()
            month_start = today.replace(day=1)
            payments = payments.filter(payment_date__gte=month_start, payment_date__lte=today)

    # Calculate MTD Stats for Dashboard Header
    stats = _get_payment_stats(user)

    context = {
        'payments': payments.order_by('-payment_date', '-created_at'),
        'filter_form': form,
        'stats': stats,
        'title': 'Payment Management'
    }
    return render(request, 'user/payments/payment_list.html', context)

@login_required
def payment_detail(request, pk):
    user = request.user
    payment = get_object_or_404(Payment, pk=pk, member__gym=user.gym)
    
    # Branch check
    if user.role == 'branch_admin' and payment.member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('payment-list')
        
    context = {
        'payment': payment,
        'title': f"Payment Receipt: {payment.receipt_number}"
    }
    return render(request, 'user/payments/payment_detail.html', context)

@login_required
def payment_create(request):
    user = request.user
    if request.method == 'POST':
        form = PaymentForm(request.POST, user=user)
        if form.is_valid():
            payment = form.save(commit=False)
            # Basic validation: ensure member belongs to gym
            if payment.member.gym != user.gym:
                messages.error(request, "Invalid member selected.")
            else:
                payment.save() # save() also updates subscription status
                messages.success(request, f"Payment recorded successfully: {payment.receipt_number}")
                return redirect('payment-list')
    else:
        form = PaymentForm(user=user)
        
    context = {
        'form': form,
        'title': 'Record New Payment'
    }
    return render(request, 'user/payments/payment_form.html', context)

@login_required
def payment_invoice(request, pk):
    """Professional Invoice View"""
    user = request.user
    payment = get_object_or_404(Payment, pk=pk, member__gym=user.gym)
    
    # Branch check
    if user.role == 'branch_admin' and payment.member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('payment-list')
        
    gym = user.gym
    branch = payment.member.branch
    subscription = payment.subscription
    total_discount = subscription.base_amount - subscription.final_amount
    
    context = {
        'payment': payment,
        'gym': gym,
        'branch': branch,
        'member': payment.member,
        'subscription': subscription,
        'total_discount': total_discount,
        'title': f"Invoice - {payment.receipt_number}"
    }
    return render(request, 'user/payments/invoice.html', context)

def _get_payment_stats(user):
    """Helper for payment statistics"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    base_payments = Payment.objects.filter(member__gym=user.gym, status='Completed')
    base_installments = SubscriptionInstallment.objects.filter(subscription__member__gym=user.gym)
    base_subscriptions = Subscription.objects.filter(member__gym=user.gym)

    if user.role == 'branch_admin' and user.branch:
        base_payments = base_payments.filter(member__branch=user.branch)
        base_installments = base_installments.filter(subscription__member__branch=user.branch)
        base_subscriptions = base_subscriptions.filter(member__branch=user.branch)

    total_mtd = base_payments.filter(payment_date__gte=month_start).aggregate(sum=Sum('amount'))['sum'] or 0
    total_prev = base_payments.filter(payment_date__gte=prev_month_start, payment_date__lte=prev_month_end).aggregate(sum=Sum('amount'))['sum'] or 0
    
    pending_mtd_list = base_installments.filter(due_date__gte=month_start, due_date__lte=today, status__in=['Pending', 'Partially Paid'])
    pending_sum = sum(inst.remaining_amount for inst in pending_mtd_list)

    overdue_mtd_list = base_installments.filter(due_date__lt=today, status__in=['Pending', 'Partially Paid', 'Overdue'])
    overdue_sum = sum(inst.remaining_amount for inst in overdue_mtd_list)

    subs_mtd = base_subscriptions.filter(created_at__date__gte=month_start)
    discounts_sum = sum((s.base_amount - s.final_amount) for s in subs_mtd)

    return {
        'total_collected_mtd': total_mtd,
        'total_collected_prev_month': total_prev,
        'pending_due_mtd': pending_sum,
        'overdue_mtd': overdue_sum,
        'discounts_mtd': discounts_sum
    }

from django.http import JsonResponse
@login_required
def ajax_member_data(request, member_id):
    """
    Session-authenticated AJAX endpoint to fetch member subscriptions and installments
    for the payment creation form dropdowns.
    """
    user = request.user
    if not user.gym:
        return JsonResponse({"error": "No gym associated", "subscriptions": []}, status=400)
    
    member = get_object_or_404(Member, pk=member_id, gym=user.gym)
    
    if user.role == 'branch_admin' and member.branch != user.branch:
        return JsonResponse({"error": "Access denied", "subscriptions": []}, status=403)
        
    subs = Subscription.objects.filter(member=member)
    
    data = []
    for sub in subs:
        installments = []
        for inst in sub.installments.all():
            installments.append({
                "id": inst.id,
                "installment_number": inst.installment_number,
                "due_date": inst.due_date.strftime("%Y-%m-%d") if inst.due_date else None,
                "remaining_amount": float(inst.remaining_amount),
                "status": inst.status
            })
            
        data.append({
            "id": sub.id,
            "subscription_type_name": sub.subscription_type.name if sub.subscription_type else "Custom",
            "start_date": sub.start_date.strftime("%Y-%m-%d") if sub.start_date else None,
            "end_date": sub.end_date.strftime("%Y-%m-%d") if sub.end_date else None,
            "balance_amount": float(sub.balance_amount),
            "installments": installments
        })
        
    return JsonResponse({"subscriptions": data})
