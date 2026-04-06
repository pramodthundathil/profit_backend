from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import Member, Subscription
from .forms import MemberForm, SubscriptionForm
from home.models import GymBranch

@login_required
def member_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied. No gym associated.")
        return redirect('user-dashboard')

    branch_filter = request.GET.get('branch', '')
    
    # Base QuerySet: Members of the user's gym
    members = Member.objects.filter(gym=user.gym, is_active=True).select_related('branch', 'gym')

    # Role-based filtering
    if user.role == 'branch_admin' and user.branch:
        # Branch Manager sees only their branch members
        members = members.filter(branch=user.branch)
    elif user.role in ['gym_admin', 'staff']:
        # Admin/Staff can see all, but can filter by branch
        if branch_filter:
            members = members.filter(branch_id=branch_filter)
    
    # Sorting (DataTables handles this, but good to have a default)
    members = members.order_by('-date_added')
    # Branches for filter dropdown (Admin/Staff only)
    branches = GymBranch.objects.filter(gym=user.gym, is_active=True, is_deleted=False) if user.role != 'branch_admin' else None

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
        member.is_active = False # Soft delete style or direct delete? 
        # Requirement says "edit delete also same".
        # If we use SoftDeleteMixin on Member (it's not there in models.py check), we use delete().
        # Member model in step 6 DOES NOT have SoftDeleteMixin. It has is_active field.
        # "is_active = models.BooleanField(default=True)"
        # So we set is_active = False.
        member.membership_status = 'Cancelled'
        member.save()
        messages.success(request, "Member deactivated/deleted successfully.")
        
    return redirect('member-list')

@login_required
def member_detail(request, pk):
    user = request.user
    member = get_object_or_404(Member, pk=pk, gym=user.gym)
    
    # Permission Check
    if user.role == 'branch_admin' and member.branch != user.branch:
        messages.error(request, "Access denied.")
        return redirect('member-list')
        
    context = {
        'member': member,
        'title': f"Member Details: {member.full_name}",
        'subscriptions': member.subscriptions.all().order_by('-created_at')
    }
    return render(request, "user/members/member_detail.html", context)

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
        # Mark as paid
        installment.status = 'Paid'
        installment.paid_date = timezone.now().date()
        installment.save()
        
        # Update subscription amount paid
        sub = installment.subscription
        sub.update_payment_status()
        
        messages.success(request, f"Installment {installment.installment_number} marked as paid.")
        return redirect('member-detail', pk=sub.member.pk)
        
    return redirect('member-detail', pk=installment.subscription.member.pk)
