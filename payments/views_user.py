from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Payment, GymOffer
from .forms import PaymentForm, PaymentFilterForm, GymOfferForm
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
                # Automatic Offer Application
                today = timezone.now().date()
                active_offer = GymOffer.objects.filter(
                    gym=user.gym,
                    is_active=True,
                    start_date__lte=today,
                    end_date__gte=today
                ).first()
                
                # Check if specific to certain members
                if active_offer and active_offer.specific_members.exists():
                    if not active_offer.specific_members.filter(id=payment.member.id).exists():
                        active_offer = None

                if active_offer:
                    # Check if it's a Full Payment (considering discount)
                    # New Logic: threshold = balance * (1 - percentage/100)
                    is_full_payment = False
                    balance_to_check = Decimal('0.00')
                    
                    if payment.installment:
                        balance_to_check = payment.installment.remaining_amount
                    else:
                        balance_to_check = payment.subscription.balance_amount
                    
                    # Calculate required amount to clear balance
                    discount_rate = active_offer.discount_percentage / 100
                    # Standardize rounding to compare exactly with UI values
                    offer_price = (balance_to_check * (1 - discount_rate)).quantize(Decimal('0.01'))
                    
                    if payment.amount >= offer_price:
                        is_full_payment = True
                        # Discount is the remaining part of the balance to reach exactly 0.00
                        payment.offer = active_offer
                        payment.discount_amount = balance_to_check - payment.amount
                        
                        # Extra safety: Ensure if they paid exactly offer_price, 
                        # discount_amount + amount = initial_balance
                    else:
                        active_offer = None # Not a full payment

                payment.save() # save() update statuses
                
                # Re-check status for message clarity
                if payment.installment:
                    payment.installment.update_payment_status()
                
                messages.success(request, f"Payment recorded successfully: {payment.receipt_number}")
                if active_offer:
                    messages.info(request, f"Offer applied: {active_offer.name}. Full balance cleared with {active_offer.discount_percentage}% discount benefit.")
                else:
                    messages.info(request, "Tip: Pay the discounted 'Offer Price' to clear the full balance instantly.")
                return redirect('payment-list')
    else:
        form = PaymentForm(user=user)
        
    # Fetch Best Active Offer for visibility in form (if possible without selected member)
    # Note: Global offer only as we don't know the member yet in initial GET
    active_offers = GymOffer.objects.filter(
        gym=user.gym,
        is_active=True,
        specific_members__isnull=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    )
    
    context = {
        'form': form,
        'title': 'Record New Payment',
        'active_offers': active_offers
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
    subscription_discount = subscription.base_amount - subscription.final_amount
    offer_discount = payment.discount_amount
    
    context = {
        'payment': payment,
        'gym': gym,
        'branch': branch,
        'member': payment.member,
        'subscription': subscription,
        'subscription_discount': subscription_discount,
        'offer_discount': offer_discount,
        'total_credit': payment.amount + offer_discount,
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
    
    # Best Offer for this member
    best_offer = GymOffer.get_active_offer(user.gym, member)
    offer_data = None
    if best_offer:
        offer_data = {
            "name": best_offer.name,
            "percentage": float(best_offer.discount_percentage)
        }
        
    data = []
    for sub in subs:
        installments = []
        for inst in sub.installments.all():
            rem = float(inst.remaining_amount)
            offer_price = rem
            if best_offer:
                offer_price = float(Decimal(str(rem)) * (1 - best_offer.discount_percentage/100))

            installments.append({
                "id": inst.id,
                "installment_number": inst.installment_number,
                "due_date": inst.due_date.strftime("%Y-%m-%d") if inst.due_date else None,
                "remaining_amount": rem,
                "offer_price": round(offer_price, 2),
                "status": inst.status
            })
            
        bal = float(sub.balance_amount)
        offer_price_bal = bal
        if best_offer:
            offer_price_bal = float(Decimal(str(bal)) * (1 - best_offer.discount_percentage/100))

        data.append({
            "id": sub.id,
            "subscription_type_name": sub.subscription_type.name if sub.subscription_type else "Custom",
            "start_date": sub.start_date.strftime("%Y-%m-%d") if sub.start_date else None,
            "end_date": sub.end_date.strftime("%Y-%m-%d") if sub.end_date else None,
            "balance_amount": bal,
            "offer_price": round(offer_price_bal, 2),
            "installments": installments
        })
        
    return JsonResponse({
        "subscriptions": data,
        "active_offer": offer_data
    })


# ============================================================================
# OFFER VIEWS (Admin Only)
# ============================================================================

from django.contrib.auth.decorators import user_passes_test

def is_gym_admin(user):
    return user.is_authenticated and user.role == 'gym_admin'

@login_required
@user_passes_test(is_gym_admin)
def offer_list(request):
    user = request.user
    offers = GymOffer.objects.filter(gym=user.gym)
    
    context = {
        'offers': offers,
        'title': 'Offer Management'
    }
    return render(request, 'user/payments/offer_list.html', context)

@login_required
@user_passes_test(is_gym_admin)
def offer_create(request):
    user = request.user
    if request.method == 'POST':
        form = GymOfferForm(request.POST, user=user)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.gym = user.gym
            offer.save()
            form.save_m2m()
            messages.success(request, "Offer created successfully.")
            return redirect('offer-list')
    else:
        form = GymOfferForm(user=user)
        
    context = {
        'form': form,
        'title': 'Create New Offer'
    }
    return render(request, 'user/payments/offer_form.html', context)

@login_required
@user_passes_test(is_gym_admin)
def offer_edit(request, pk):
    user = request.user
    offer = get_object_or_404(GymOffer, pk=pk, gym=user.gym)
    
    if request.method == 'POST':
        form = GymOfferForm(request.POST, instance=offer, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Offer updated successfully.")
            return redirect('offer-list')
    else:
        form = GymOfferForm(instance=offer, user=user)
        
    context = {
        'form': form,
        'offer': offer,
        'title': 'Edit Offer'
    }
    return render(request, 'user/payments/offer_form.html', context)

@login_required
@user_passes_test(is_gym_admin)
def offer_delete(request, pk):
    user = request.user
    offer = get_object_or_404(GymOffer, pk=pk, gym=user.gym)
    
    if request.method == 'POST':
        offer.delete()
        messages.success(request, "Offer deleted successfully.")
        return redirect('offer-list')
        
    return render(request, 'user/payments/offer_confirm_delete.html', {'offer': offer})
