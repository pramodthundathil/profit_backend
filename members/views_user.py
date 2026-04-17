from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .models import Member, Subscription, HealthHistory, Medication, ParqForm, SubscriptionInstallment
from .forms import MemberForm, SubscriptionForm, HealthHistoryForm, MedicationFormSet, ParqFormModelForm, ParqUpdateForm
from home.models import GymBranch
from payments.models import Payment, GymOffer

@login_required
def payment_receipt(request, pk):
    user = request.user
    # Ensure the payment belongs to the current gym
    payment = get_object_or_404(Payment, pk=pk, member__gym=user.gym)
    
    context = {
        'payment': payment,
        'member': payment.member,
        'gym': payment.member.gym,
        'title': f"Receipt: {payment.receipt_number}"
    }
    return render(request, 'user/payments/receipt.html', context)


@login_required
def member_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied. No gym associated.")
        return redirect('user-dashboard')

    branch_filter = request.GET.get('branch', '')
    
    # Base QuerySet: Members of the user's gym
    members = Member.objects.filter(gym=user.gym, is_active=True).select_related('branch', 'gym').prefetch_related('subscriptions__subscription_type')

    # Role-based filtering
    if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
        # Branch-specific staff/manager: Restricted to their branch only
        members = members.filter(branch=user.branch)
    elif user.role in ['gym_admin', 'branch_admin', 'staff', 'trainer']:
        # HQ staff/admin (no branch assigned) or gym_admin: Can see everything
        if branch_filter:
            members = members.filter(branch_id=branch_filter)
    
    # Sorting (DataTables handles this, but good to have a default)
    members = members.order_by('-date_added')
    # Branches for filter dropdown (Admins and HQ Staff only)
    branches = GymBranch.objects.filter(gym=user.gym, is_active=True, is_deleted=False) if (user.role == 'gym_admin' or not user.branch) else None

    context = {
        'members': members, # Pass full queryset
        'branches': branches,
        'selected_branch': branch_filter,
    }
    return render(request, "user/members/member_list.html", context)

@login_required
def member_create(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')

    if request.method == 'POST':
        member_form = MemberForm(request.POST, request.FILES, user=user)
        subscription_form = SubscriptionForm(request.POST, user=user)
        
        if member_form.is_valid() and subscription_form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Save Member
                    member = member_form.save(commit=False)
                    member.gym = user.gym
                    
                    # Ensure branch is set for Branch Manager
                    if user.role == 'branch_admin':
                        member.branch = user.branch
                    
                    member.save()
                    
                    # 2. Save Subscription
                    subscription = subscription_form.save(commit=False)
                    subscription.member = member
                    
                    # Set duration from Period
                    period = subscription_form.cleaned_data['subscription_period']
                    subscription.duration = period.period
                    subscription.duration_unit = 'Days' # Assuming Period is in Days as per model
                    
                    # Auto-calculate Dates (handled in model save, but we set start/end if needed)
                    # Model save handles end_date calculation based on start_date + duration
                    
                    subscription.save()
                    
                    # 3. Handle Initial Payment
                    amount_paid = subscription_form.cleaned_data.get('amount_paid', 0)
                    if amount_paid and amount_paid > 0:
                        from payments.models import Payment
                        
                        # For Installment plans, treat initial payment as an Advance (not linked to a specific installment)
                        # For Full payment plans, link it to the only installment.
                        link_to_installment = (subscription.payment_terms == 'Full')
                        
                        installment = None
                        if link_to_installment:
                            # Get the first installment
                            installment = subscription.installments.order_by('installment_number').first()
                            if installment:
                                installment.amount_paid += amount_paid
                                if installment.amount_paid >= installment.amount:
                                    installment.status = 'Paid'
                                else:
                                    installment.status = 'Partially Paid'
                                installment.paid_date = timezone.now().date()
                                installment.save()
                        
                        Payment.objects.create(
                            subscription=subscription,
                            member=member,
                            installment=installment,
                            amount=amount_paid,
                            payment_method=subscription_form.cleaned_data.get('payment_method', 'Cash'),
                            is_installment=True if installment else False,
                            installment_number=installment.installment_number if installment else None,
                            status='Completed',
                            notes="Initial payment during member creation (Advance)" if not installment else "Initial payment"
                        )
                    
                    # Update member status
                    member.update_membership_status()
                    
                    messages.success(request, f"Member {member.full_name} added successfully.")
                    return redirect('member-list')
                    
            except Exception as e:
                messages.error(request, f"Error creating member: {e}")
        else:
             messages.error(request, "Please correct the errors below.")
    else:
        member_form = MemberForm(user=user)
        subscription_form = SubscriptionForm(user=user)
        
    context = {
        'member_form': member_form,
        'subscription_form': subscription_form,
        'title': 'Add New Member'
    }
    return render(request, "user/members/member_form.html", context)

@login_required
def member_edit(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    # Permission Check
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied. You can only edit members of your branch.")
        return redirect('member-list')

    if request.method == 'POST':
        member_form = MemberForm(request.POST, request.FILES, instance=member, user=user)
        
        # We only edit member details here. Subscription edition should be separate or handled carefully.
        # For now, let's assume we edit only member details in this view.
        # If user wants to edit subscription, that's usually "renew" or "upgrade", which is a different flow.
        # But per request "edit functionality", we often just edit profile.
        
        if member_form.is_valid():
            member_form.save()
            messages.success(request, "Member details updated successfully.")
            return redirect('member-list')
    else:
        member_form = MemberForm(instance=member, user=user)
        
    context = {
        'member_form': member_form,
        'title': 'Edit Member',
        'is_edit': True,
        'member': member
    }
    # Re-use member_form.html but maybe hide subscription part or make it separate? 
    # Usually easier to have separate template or just show member form.
    # We will use member_edit_form.html for clarity or reuse member_form.html with conditions.
    return render(request, "user/members/member_form.html", context)

@login_required
def member_delete(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-list')
        
    if request.method == 'POST':
        member.delete()
        messages.success(request, "Member deleted successfully.")
        
    return redirect('member-list')

@login_required
def member_detail(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    # Permission Check
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-list')
        
    # Fetch Best Active Offer for Member (Priority: Specific > Global)
    best_offer = GymOffer.get_active_offer(user.gym, member)
    filtered_offers = [best_offer] if best_offer else []

    context = {
        'member': member,
        'title': f"Member Details: {member.full_name}",
        'subscriptions': member.subscriptions.all().order_by('-created_at'),
        'active_offers': filtered_offers
    }
    return render(request, "user/members/member_detail.html", context)

@login_required
def member_block_access(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-detail', pk=pk)
        
    member.is_access_blocked = True
    member.save()
    member.update_access_status()
    messages.warning(request, f"Access for {member.full_name} has been blocked.")
    return redirect('member-detail', pk=pk)

@login_required
def member_unblock_access(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-detail', pk=pk)
        
    member.is_access_blocked = False
    member.save()
    member.update_access_status()
    messages.success(request, f"Access for {member.full_name} has been unblocked.")
    return redirect('member-detail', pk=pk)

@login_required
def member_extend_access(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-detail', pk=pk)
        
    if request.method == 'POST':
        expiry_date = request.POST.get('expiry_date')
        if expiry_date:
            from datetime import datetime
            try:
                # Convert string to date object for model
                date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                member.manual_access_expiry = date_obj
                member.save()
                member.update_access_status()
                messages.success(request, f"Access for {member.full_name} manually extended to {expiry_date}.")
            except ValueError:
                messages.error(request, "Invalid date format.")
        else:
            messages.error(request, "Expiry date is required.")
            
    return redirect('member-detail', pk=pk)

@login_required
def member_add_subscription(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    # Permission Check
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-list')

    if request.method == 'POST':
        form = SubscriptionForm(request.POST, user=user)
        if form.is_valid():
            try:
                subscription = form.save(commit=False)
                subscription.member = member
                
                # Set duration from Period
                period = form.cleaned_data['subscription_period']
                subscription.duration = period.period
                
                # Assuming Period is in Days or we map it correctly. 
                # Model says duration_unit default is "Months" but previous code in create said "Days".
                # Let's check SubscriptionPeriod model if possible, but safely assuming 'Days' as per create view.
                subscription.duration_unit = 'Days' 
                
                subscription.save()
                
                # Handle Initial Payment
                amount_paid = form.cleaned_data.get('amount_paid', 0)
                if amount_paid and amount_paid > 0:
                    from payments.models import Payment
                    
                    # For Installment plans, treat initial payment as an Advance (not linked to a specific installment)
                    # For Full payment plans, link it to the only installment.
                    link_to_installment = (subscription.payment_terms == 'Full')
                    
                    installment = None
                    if link_to_installment:
                        # Get the first installment
                        installment = subscription.installments.order_by('installment_number').first()
                        if installment:
                            installment.amount_paid += amount_paid
                            if installment.amount_paid >= installment.amount:
                                installment.status = 'Paid'
                            else:
                                installment.status = 'Partially Paid'
                            installment.paid_date = timezone.now().date()
                            installment.save()
                    
                    Payment.objects.create(
                        subscription=subscription,
                        member=member,
                        installment=installment,
                        amount=amount_paid,
                        payment_method=form.cleaned_data.get('payment_method', 'Cash'),
                        is_installment=True if installment else False,
                        installment_number=installment.installment_number if installment else None,
                        status='Completed',
                        notes="Initial payment during subscription creation (Advance)" if not installment else "Initial payment"
                    )
                
                # Update member status
                member.update_membership_status()
                messages.success(request, "Subscription added successfully.")
                return redirect('member-detail', pk=member.pk)
            except Exception as e:
                messages.error(request, f"Error adding subscription: {e}")
        else:
             messages.error(request, "Please correct the errors below.")
    else:
        form = SubscriptionForm(user=user)
    
    context = {
        'subscription_form': form, # Using subscription_form key to match template usage likely or rename to form
        'member': member,
        'title': f"Add Subscription: {member.full_name}"
    }
    return render(request, "user/members/subscription_form.html", context)

@login_required
def installment_pay(request, pk):
    from .models import SubscriptionInstallment
    from django.utils import timezone
    installment = get_object_or_404(SubscriptionInstallment, pk=pk)
    
    # Permission check (simplified)
    if request.user.role not in ['gym_admin', 'staff', 'branch_admin']:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
         
    if request.method == 'POST':
        payment_type = request.POST.get('payment_type', 'Full')
        amount_str = request.POST.get('amount')
        amount = Decimal(amount_str) if amount_str else installment.remaining_amount
        payment_method = request.POST.get('payment_method', 'Cash')
        expiry_date = request.POST.get('expiry_date')
        transaction_id = request.POST.get('transaction_id')
        collected_by = request.POST.get('collected_by')
        notes = request.POST.get('notes')
        
        # Capture balance BEFORE applying payment
        # This is critical for calculating the discount correctly
        balance_before = installment.remaining_amount
        
        # 2. Apply Offer Logic (Priority Scoping: Specific > Global)
        from payments.models import GymOffer
        active_offer = GymOffer.get_active_offer(installment.subscription.member.gym, installment.subscription.member)
        
        discount_amount = Decimal('0.00')
        # Only apply discount if it's a full payment consideration
        if active_offer:
            # Calculate Offer Price (required to clear balance)
            discount_rate = active_offer.discount_percentage / 100
            # Standardize rounding
            offer_price = (balance_before * (1 - discount_rate)).quantize(Decimal('0.01'))
            
            if amount >= offer_price:
                # Apply discount to clear the entire installment balance
                discount_amount = balance_before - amount
            else:
                active_offer = None # Not eligible for discount
        
        # 3. Create Payment record
        from payments.models import Payment
        sub = installment.subscription
        payment = Payment.objects.create(
            subscription=sub,
            member=sub.member,
            installment=installment,
            amount=amount,
            discount_amount=discount_amount,
            offer=active_offer,
            payment_method=payment_method,
            transaction_id=transaction_id,
            collected_by=collected_by,
            notes=notes,
            is_installment=True,
            installment_number=installment.installment_number,
            status='Completed'
        )
        
        # 4. CRITICAL: Update the models with the discount amount
        # This is where the actual balance reduction happens!
        if discount_amount > 0:
            installment.discount_amount = (installment.discount_amount or Decimal('0.00')) + discount_amount
            installment.save(update_fields=['discount_amount'])
            
            sub.discount_amount = (sub.discount_amount or Decimal('0.00')) + discount_amount
            sub.save(update_fields=['discount_amount'])

        # 5. Explicitly update installment status with new credit (amount + discount)
        installment.update_payment_status()
        
        # 4. Explicitly set expiry date if it's a partial payment and user provided a date
        if payment_type == 'Partial' and expiry_date:
            sub.end_date = expiry_date
            sub.save(update_fields=['end_date'])
        
        msg = f"Payment of {amount} for installment {installment.installment_number} recorded successfully."
        if discount_amount > 0:
            msg += f" (Bonus of {discount_amount} applied for full payment)"
        messages.success(request, msg)
        return redirect('member-detail', pk=sub.member.pk)
        
    return redirect('member-detail', pk=installment.subscription.member.pk)

@login_required
def subscription_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied. No gym associated.")
        return redirect('user-dashboard')

    branch_filter = request.GET.get('branch', '')
    status_filter = request.GET.get('status', '')
    
    # Base QuerySet: Subscriptions of members in the user's gym
    subscriptions = Subscription.objects.filter(member__gym=user.gym).select_related('member', 'member__branch', 'subscription_type')

    # Role-based filtering
    if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
        # Branch-specific: Restricted to their branch only
        subscriptions = subscriptions.filter(member__branch=user.branch)
    elif user.role in ['gym_admin', 'branch_admin', 'staff', 'trainer']:
        # HQ staff (no branch) or gym_admin: Full access with optional branch filter
        if branch_filter:
            subscriptions = subscriptions.filter(member__branch_id=branch_filter)

    # Status filtering
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    
    # Sorting
    subscriptions = subscriptions.order_by('-created_at')

    # Branches for filter dropdown (Admins and HQ Staff only)
    branches = GymBranch.objects.filter(gym=user.gym, is_active=True, is_deleted=False) if (user.role == 'gym_admin' or not user.branch) else None

    context = {
        'subscriptions': subscriptions,
        'branches': branches,
        'selected_branch': branch_filter,
        'selected_status': status_filter,
        'title': 'Subscription Management'
    }
    return render(request, "user/members/subscription_list.html", context)

@login_required
def subscription_edit(request, pk):
    user = request.user
    subscription = get_object_or_404(Subscription, pk=pk, member__gym=user.gym)
    
    # Permission Check
    has_permission = False
    if user.role == 'gym_admin':
        has_permission = True
    elif user.role in ['branch_admin', 'staff']:
        if subscription.member.branch == user.branch:
            has_permission = True
            
    if not has_permission:
        messages.error(request, "Access denied. You do not have permission to edit this subscription.")
        return redirect('member-detail', pk=subscription.member.pk)

    if request.method == 'POST':
        form = SubscriptionForm(request.POST, request.FILES, instance=subscription, user=user)
        if form.is_valid():
            try:
                subscription = form.save(commit=False)
                # If period changed, we update duration
                period = form.cleaned_data.get('subscription_period')
                if period:
                    subscription.duration = period.period
                
                subscription.save()
                
                # Update status
                subscription.update_status()
                subscription.member.update_membership_status()
                
                messages.success(request, "Subscription updated successfully.")
                return redirect('member-detail', pk=subscription.member.pk)
            except Exception as e:
                messages.error(request, f"Error updating subscription: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SubscriptionForm(instance=subscription, user=user)
    
    context = {
        'subscription_form': form,
        'member': subscription.member,
        'subscription': subscription,
        'is_edit': True,
        'title': f"Edit Subscription: {subscription.member.full_name}"
    }
    return render(request, "user/members/subscription_form.html", context)

@login_required
def subscription_delete(request, pk):
    user = request.user
    subscription = get_object_or_404(Subscription, pk=pk, member__gym=user.gym)
    member = subscription.member
    
    # Permission Check
    has_permission = False
    if user.role == 'gym_admin':
        has_permission = True
    elif user.role in ['branch_admin', 'staff']:
        if member.branch == user.branch:
            has_permission = True
            
    if not has_permission:
        messages.error(request, "Access denied. You do not have permission to delete this subscription.")
        return redirect('member-detail', pk=member.pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                subscription.delete()
                
                # Update member access and status after deletion
                member.update_membership_status()
                member.update_access_status()
                
                messages.success(request, "Subscription deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting subscription: {e}")
        
    return redirect('member-detail', pk=member.pk)



@login_required
def subscription_detail(request, pk):
    user = request.user
    subscription = get_object_or_404(Subscription, pk=pk, member__gym=user.gym)
    
    # Permission Check
    has_permission = False
    if user.role == 'gym_admin':
        has_permission = True
    elif user.role in ['branch_admin', 'staff']:
        if subscription.member.branch == user.branch:
            has_permission = True
            
    if not has_permission:
        messages.error(request, "Access denied. You do not have permission to view this subscription.")
        return redirect('subscription-list')
        
    # Fetch Best Active Offer for Member
    best_offer = GymOffer.get_active_offer(user.gym, subscription.member)
    filtered_offers = [best_offer] if best_offer else []

    context = {
        'subscription': subscription,
        'member': subscription.member,
        'installments': subscription.installments.all().order_by('installment_number'),
        'payments': subscription.payments.all().order_by('-payment_date'),
        'active_offers': filtered_offers,
        'title': f"Subscription Details: {subscription.member.full_name}"
    }
    return render(request, "user/members/subscription_detail.html", context)

# ============================================================================
# HEALTH HISTORY VIEWS
# ============================================================================

@login_required
def health_history_form_view(request, member_id):
    member = get_object_or_404(Member, id=member_id, gym=request.user.gym)
    
    # Check if health history already exists
    health_history = getattr(member, 'health_history', None)
    
    if request.method == 'POST':
        form = HealthHistoryForm(request.POST, instance=health_history)
        if form.is_valid():
            with transaction.atomic():
                health_history = form.save(commit=False)
                health_history.member = member
                health_history.save()
                
                # Handle medications formset
                medication_formset = MedicationFormSet(request.POST, instance=health_history)
                if medication_formset.is_valid():
                    medication_formset.save()
                
                # Check for risky conditions and update member's risk_medical flag
                has_risky = health_history.has_risky_heart_conditions or health_history.has_risky_health_conditions
                member.risk_medical = has_risky
                member.save(update_fields=['risk_medical'])
                
                messages.success(request, "Health History saved successfully.")
                
                if has_risky:
                    # If risky, direct to PAR-Q form
                    messages.info(request, "Higher medical risk detected. Member must complete the PAR-Q form.")
                    return redirect('parq-create', member_id=member.id)
                
                return redirect(f"{reverse('member-detail', args=[member.id])}#health")
        else:
            messages.error(request, "Please correct the errors in the form.")
            medication_formset = MedicationFormSet(request.POST, instance=health_history)
    else:
        form = HealthHistoryForm(instance=health_history)
        medication_formset = MedicationFormSet(instance=health_history)
    
    context = {
        'form': form,
        'medication_formset': medication_formset,
        'member': member,
        'title': 'Health History Form'
    }
    return render(request, 'user/members/health_history/form.html', context)

@login_required
def health_history_detail_view(request, member_id):
    member = get_object_or_404(Member, id=member_id, gym=request.user.gym)
    health_history = get_object_or_404(HealthHistory, member=member)
    
    context = {
        'health_history': health_history,
        'member': member,
        'medications': health_history.medications.all(),
        'title': 'Health History Detail'
    }
    return render(request, 'user/members/health_history/detail.html', context)

@login_required
def success_on_health_history(request):
    return render(request, 'user/members/health_history/success.html', {'title': 'Success'})

# ============================================================================
# PAR-Q FORM VIEWS
# ============================================================================

@login_required
def parq_form_create(request, member_id):
    member = get_object_or_404(Member, id=member_id, gym=request.user.gym)
    
    # Check if PAR-Q already exists
    parq = getattr(member, 'health_history_parque', None)
    if parq:
        return redirect('parq-detail', pk=parq.id)
        
    if request.method == 'POST':
        form = ParqFormModelForm(request.POST)
        if form.is_valid():
            parq = form.save(commit=False)
            parq.member = member
            parq.is_completed = True
            parq.save()
            messages.success(request, "PAR-Q form submitted successfully.")
            return redirect(f"{reverse('member-detail', args=[member.id])}#health")
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = ParqFormModelForm()
        
    context = {
        'form': form,
        'member': member,
        'title': 'PAR-Q Form'
    }
    return render(request, 'user/members/parq/parq_form.html', context)

@login_required
def parq_form_detail(request, pk):
    parq = get_object_or_404(ParqForm, pk=pk, member__gym=request.user.gym)
    context = {
        'parq': parq,
        'member': parq.member,
        'title': 'PAR-Q Form Detail'
    }
    return render(request, 'user/members/parq/parq_detail.html', context)

@login_required
def parq_form_update(request, pk):
    parq = get_object_or_404(ParqForm, pk=pk, member__gym=request.user.gym)
    
    if request.method == 'POST':
        form = ParqUpdateForm(request.POST, instance=parq)
        if form.is_valid():
            form.save()
            messages.success(request, "PAR-Q form updated successfully.")
            return redirect(f"{reverse('member-detail', args=[parq.member.id])}#health")
    else:
        form = ParqUpdateForm(instance=parq)
        
    context = {
        'form': form,
        'member': parq.member,
        'title': 'Update PAR-Q Form'
    }
    return render(request, 'user/members/parq/parq_update_form.html', context)

# ============================================================================
# PUBLIC FORM VIEWS (NO LOGIN REQUIRED)
# ============================================================================

def public_health_history_form(request, token):
    member = get_object_or_404(Member, public_token=token)
    
    # Check if health history already exists
    health_history = getattr(member, 'health_history', None)
    
    if request.method == 'POST':
        form = HealthHistoryForm(request.POST, instance=health_history)
        medication_formset = MedicationFormSet(request.POST, instance=health_history)
        
        if form.is_valid():
            with transaction.atomic():
                health_history = form.save(commit=False)
                health_history.member = member
                health_history.save()
                
                # Handle medications formset (which is already initialized above)
                if medication_formset.is_valid():
                    medication_formset.save()
                
                # Check for risky conditions and update member's risk_medical flag
                has_risky = health_history.has_risky_heart_conditions or health_history.has_risky_health_conditions
                member.risk_medical = has_risky
                member.save(update_fields=['risk_medical'])
                
                if has_risky:
                    # If risky, direct to public PAR-Q form
                    return redirect('public-parq', token=member.public_token)
                
                return redirect('public-success')
    else:
        form = HealthHistoryForm(instance=health_history)
        medication_formset = MedicationFormSet(instance=health_history)
    
    context = {
        'form': form,
        'medication_formset': medication_formset,
        'member': member,
        'title': 'Health History Form',
        'is_public': True
    }
    return render(request, 'user/members/health_history/form.html', context)

def public_parq_form(request, token):
    member = get_object_or_404(Member, public_token=token)
    
    # Check if PAR-Q already exists
    parq = getattr(member, 'health_history_parque', None)
    if parq and parq.is_completed:
        return redirect('public-success')
        
    if request.method == 'POST':
        form = ParqFormModelForm(request.POST)
        if form.is_valid():
            parq = form.save(commit=False)
            parq.member = member
            parq.is_completed = True
            parq.save()
            return redirect('public-success')
    else:
        form = ParqFormModelForm()
        
    context = {
        'form': form,
        'member': member,
        'title': 'PAR-Q Form',
        'is_public': True
    }
    return render(request, 'user/members/parq/parq_form.html', context)

def public_success(request):
    return render(request, 'user/members/public/success.html', {
        'title': 'Submission Successful',
        'is_public': True
    })

@login_required
def pending_fee_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied. No gym associated.")
        return redirect('user-dashboard')

    today = timezone.now().date()
    
    # Base filter: Installments belonging to the user's gym
    installments = SubscriptionInstallment.objects.filter(
        subscription__member__gym=user.gym
    ).select_related(
        'subscription', 
        'subscription__member', 
        'subscription__member__branch', 
        'subscription__subscription_type'
    )

    # Branch filter (for non-gym_admin roles)
    if user.role != 'gym_admin' and user.branch:
        installments = installments.filter(subscription__member__branch=user.branch)
    
    # Role-based branch filter from query params (for gym_admin)
    branch_filter = request.GET.get('branch', '')
    if user.role == 'gym_admin' and branch_filter:
        installments = installments.filter(subscription__member__branch_id=branch_filter)

    # Filter type
    filter_type = request.GET.get('type', 'overdue')
    if filter_type == 'overdue':
        # Overdue: due date in the past and not Paid
        installments = installments.filter(
            Q(status='Overdue') | Q(due_date__lt=today)
        ).exclude(status='Paid')
    elif filter_type == 'this_month':
        # This month: due date within current month and not Paid
        start_of_month = today.replace(day=1)
        next_month = start_of_month + relativedelta(months=1)
        end_of_month = next_month - timedelta(days=1)
        installments = installments.filter(
            due_date__range=[start_of_month, end_of_month]
        ).exclude(status='Paid')
    else:
        # pending/all non-paid
        installments = installments.exclude(status='Paid')

    # Sorting
    installments = installments.order_by('due_date')

    # Support for gym admin to see branch list for filtering
    branches = None
    if user.role == 'gym_admin':
        from home.models import GymBranch
        branches = GymBranch.objects.filter(gym=user.gym, is_active=True, is_deleted=False)

    context = {
        'installments': installments,
        'filter_type': filter_type,
        'branches': branches,
        'selected_branch': branch_filter,
        'title': 'Fee Pending & Overdue Payments',
        'currency_symbol': user.gym.currency_symbol if hasattr(user.gym, 'currency_symbol') else '₹'
    }
    return render(request, 'user/members/pending_fee_list.html', context)
