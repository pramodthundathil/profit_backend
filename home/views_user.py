from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from datetime import datetime, date
from .models import GymOffice, CustomUser, PaymentTransaction, SubscriptionHistory, HikConfigurationDb, GymBranch
from members.models import Member, Subscription
from payments.models import Payment

from .forms import GymBranchForm, GymUserForm, HikConfigurationForm, GymUserEditForm


@login_required
@login_required
def user_dashboard(request):
    user = request.user
    if not user.gym:
        return render(request, "user/dashboard.html", {})

    gym = user.gym
    
    # --- Filter Handling ---
    # Default to current month/year
    today = timezone.now().date()
    current_month = int(request.GET.get('month', today.month))
    current_year = int(request.GET.get('year', today.year))
    selected_branch_id = request.GET.get('branch', '')

    # Permission-based Branch Isolation
    if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
        # Restricted to their specific branch
        selected_branch_id = str(user.branch.id)
        is_restricted = True
    else:
        # Gym Admin or HQ staff (no branch assigned) can see everything
        is_restricted = False

    # --- Base Querysets with Filters ---
    members_qs = Member.objects.filter(gym=gym, is_active=True).prefetch_related('subscriptions__subscription_type')
    subscriptions_qs = Subscription.objects.filter(member__gym=gym)
    payments_qs = Payment.objects.filter(member__gym=gym, status='Completed')

    if is_restricted:
        # Strict filter for restricted roles (Branch)
        members_qs = members_qs.filter(branch=user.branch)
        subscriptions_qs = subscriptions_qs.filter(member__branch=user.branch)
        payments_qs = payments_qs.filter(member__branch=user.branch)
    elif selected_branch_id:
        # Optional filter for Gym Admin or HQ staff
        members_qs = members_qs.filter(branch_id=selected_branch_id)
        subscriptions_qs = subscriptions_qs.filter(member__branch_id=selected_branch_id)
        payments_qs = payments_qs.filter(member__branch_id=selected_branch_id)

    # --- Analytical Data Calcs ---
    
    # 1. Member Standings
    active_count = members_qs.filter(membership_status='Active').count()
    expired_count = members_qs.filter(membership_status='Expired').count()
    
    # 2. Expiring soon (Next 7 days)
    seven_days_later = today + timezone.timedelta(days=7)
    expiring_soon = subscriptions_qs.filter(
        status='Active',
        end_date__range=[today, seven_days_later]
    ).select_related('member')

    # 3. New Registrations for selected month/year
    new_regs_this_month = members_qs.filter(
        registration_date__month=current_month,
        registration_date__year=current_year
    ).count()

    # 4. Financial Analytics (GYM ADMIN ONLY)
    financials = None
    if user.role == 'gym_admin':
        # Total Collected in selected month
        total_collected = payments_qs.filter(
            payment_date__month=current_month,
            payment_date__year=current_year
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Total Due (Active Subscriptions with balance)
        total_due = subscriptions_qs.filter(
            status='Active',
            balance_amount__gt=0
        ).aggregate(total=Sum('balance_amount'))['total'] or 0

        # Payment Methods breakdown
        payment_methods = payments_qs.filter(
            payment_date__month=current_month,
            payment_date__year=current_year
        ).values('payment_method').annotate(total=Sum('amount')).order_by('-total')

        financials = {
            'total_collected': total_collected,
            'total_due': total_due,
            'payment_methods': payment_methods
        }

    # 5. Lists for Tables
    recent_members = members_qs.order_by('-date_added')[:5]
    recent_payments = None
    if user.role == 'gym_admin':
         recent_payments = payments_qs.order_by('-payment_date', '-created_at')[:5]

    # --- Context Preparation ---
    # Prepare months for the filter dropdown
    months_list = []
    for m in range(1, 13):
        months_list.append({
            'name': datetime(2000, m, 1).strftime('%B'),
            'value': m
        })

    context = {
        'gym': gym,
        'branches': gym.gym_branches.filter(is_deleted=False),
        'selected_branch': selected_branch_id,
        'current_month': current_month,
        'current_month_name': datetime(2000, current_month, 1).strftime('%B'),
        'current_year': current_year,
        'months_list': months_list,
        'year_range': range(today.year - 2, today.year + 2),
        'is_restricted': is_restricted,
        
        # Stats
        'active_count': active_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon.count(),
        'new_registrations': new_regs_this_month,
        'expiring_soon_list': expiring_soon[:5],
        
        # Data
        'financials': financials,
        'recent_members': recent_members,
        'recent_payments': recent_payments,
        
        # Original logic (for compatibility if needed, though we replaced most of it)
        'total_staff': gym.users.filter(is_deleted=False).exclude(id=user.id).count(),
        'subscription_status': gym.get_subscription_status(),
    }
    
    return render(request, "user/dashboard.html", context)

@login_required
def subscription_expired(request):
    user = request.user
    context = {}
    
    if user.gym:
        gym = user.gym
        context['gym'] = gym
        context['status'] = gym.get_subscription_status()
        
        # Placeholder for plans - in a real app, fetch from Plan model
        context['plans'] = [
            {'name': 'Monthly Plan', 'price': 2999, 'duration': '1 Month', 'id': 'plan_monthly'},
            {'name': 'Quarterly Plan', 'price': 7999, 'duration': '3 Months', 'id': 'plan_quarterly'},
            {'name': 'Annual Plan', 'price': 24999, 'duration': '12 Months', 'id': 'plan_annual'},
        ]
        
    return render(request, "user/subscription_expired.html", context)

@login_required
def add_branch(request):
    user = request.user
    
    if not user.gym:
        messages.error(request, "Account not associated with any gym.")
        return redirect('user-dashboard')

    if request.method == 'POST':
        form = GymBranchForm(request.POST)
        form.instance.gym = user.gym
        
        # Check license limits/permissions
        if not user.gym.can_create_branch():
             messages.error(request, "Cannot create new branch. License limit reached.")
             return redirect('user-dashboard')
             
        if form.is_valid():
            branch = form.save()
            # Assign creator
            branch.created_by = user
            branch.save()
            
            messages.success(request, f"Branch '{branch.name}' added successfully.")
            return redirect('user-branch-list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymBranchForm()
        
    context = {
        'form': form,
        'gym': user.gym
    }
    return render(request, "user/add_branch.html", context) 

@login_required
def branch_list(request):
    user = request.user
    if not user.gym:
        return redirect('user-dashboard')

    # Restrict to gym_admin only
    if user.role != 'gym_admin':
        messages.error(request, "Access denied. Only Gym Administrators can view this page.")
        return redirect('user-dashboard')
        
    context = {
        'gym': user.gym,
        'branches': user.gym.gym_branches.filter(is_deleted=False)
    }
    return render(request, "user/branch_list.html", context)

@login_required
def edit_branch(request, pk):
    user = request.user
    if not user.gym or user.role != 'gym_admin':
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')

    branch = get_object_or_404(GymBranch, pk=pk, gym=user.gym, is_deleted=False)

    if request.method == 'POST':
        form = GymBranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, f"Branch '{branch.name}' updated successfully.")
            return redirect('user-branch-list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymBranchForm(instance=branch)

    context = {
        'form': form,
        'gym': user.gym,
        'branch': branch,
        'is_edit': True
    }
    return render(request, "user/add_branch.html", context)

@login_required
def delete_branch(request, pk):
    user = request.user
    if not user.gym or user.role != 'gym_admin':
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')

    branch = get_object_or_404(GymBranch, pk=pk, gym=user.gym, is_deleted=False)
    
    # Check if there are active staff in this branch? 
    # Usually soft delete cascades or we just mark it. Assuming simple soft delete.
    branch.soft_delete()
    messages.success(request, f"Branch '{branch.name}' deleted successfully.")
    return redirect('user-branch-list')


@login_required
def staff_list(request):
    user = request.user
    if not user.gym:
        return redirect('user-dashboard')
        
    # Restrict to gym_admin only
    if user.role != 'gym_admin':
        messages.error(request, "Access denied. Only Gym Administrators can view this page.")
        return redirect('user-dashboard')

    context = {
        'gym': user.gym,
        'members': user.gym.users.filter(is_deleted=False).exclude(id=user.id)
    }
    return render(request, "user/staff_list.html", context)

@login_required
def add_staff(request):
    user = request.user
    
    if not user.gym:
         messages.error(request, "Account not associated with any gym.")
         return redirect('user-dashboard')
         
    if request.method == 'POST':
        form = GymUserForm(request.POST, gym=user.gym)
        form.instance.gym = user.gym
        
        if form.is_valid():
            staff = form.save()
            messages.success(request, f"Staff member '{staff.get_full_name()}' added successfully.")
            return redirect('user-staff-list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymUserForm(gym=user.gym)
        
    context = {
        'form': form,
        'gym': user.gym
    }
    return render(request, "user/add_staff.html", context)

@login_required
def edit_staff(request, pk):
    user = request.user
    if not user.gym or user.role != 'gym_admin':
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')

    staff = get_object_or_404(CustomUser, pk=pk, gym=user.gym, is_deleted=False)
    
    # Prevent editing self through this view -> redirect to profile if implemented, or just error
    if staff.id == user.id:
         messages.error(request, "You cannot edit your own permissions here.")
         return redirect('user-staff-list')

    if request.method == 'POST':
        form = GymUserEditForm(request.POST, instance=staff, gym=user.gym)
        if form.is_valid():
            form.save()
            messages.success(request, f"Staff member '{staff.get_full_name()}' updated successfully.")
            return redirect('user-staff-list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymUserEditForm(instance=staff, gym=user.gym)

    context = {
        'form': form,
        'gym': user.gym,
        'staff_member': staff,
        'is_edit': True
    }
    # Reuse add_staff template but ensure it handles 'is_edit' logic if any (mostly for title)
    # We might need to slightly adjust add_staff.html to switch title "Add Staff" -> "Edit Staff"
    return render(request, "user/add_staff.html", context)


@login_required
def delete_staff(request, pk):
    user = request.user
    if not user.gym or user.role != 'gym_admin':
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')

    staff = get_object_or_404(CustomUser, pk=pk, gym=user.gym, is_deleted=False)
    
    if staff.id == user.id:
         messages.error(request, "You cannot delete yourself.")
         return redirect('user-staff-list')

    staff.soft_delete()
    messages.success(request, f"Staff member '{staff.get_full_name()}' deleted successfully.")
    return redirect('user-staff-list')


@login_required
def hik_config_list(request):
    user = request.user
    
    # Deny staff/trainers
    if user.role not in ['gym_admin', 'branch_admin']:
        messages.error(request, "Access denied. Only administrators can manage device configurations.")
        return redirect('user-dashboard')

    configs = HikConfigurationDb.objects.none()
    
    # Gym Admin sees all configs for their gym and branches
    if user.role == 'gym_admin' and user.gym:
        configs = HikConfigurationDb.objects.filter(
            Q(gym=user.gym) | Q(gym_branch__gym=user.gym)
        )
    # Branch Admin sees only their branch config
    elif user.role == 'branch_admin' and user.branch:
        configs = HikConfigurationDb.objects.filter(gym_branch=user.branch)
        
    context = {
        'configs': configs,
        'gym': user.gym if user.role == 'gym_admin' else (user.branch.gym if user.branch else None)
    }
    return render(request, "user/hik_config_list.html", context)


@login_required
def add_hik_config(request):
    user = request.user
    
    # Check permission
    if user.role not in ['gym_admin', 'branch_admin']:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('user-dashboard')
        
    if request.method == 'POST':
        form = HikConfigurationForm(request.POST, user=user)
        
        # Manually handle fields disabled/hidden in form logic
        if user.role == 'branch_admin':
            form.instance.gym_branch = user.branch
            # Ensure branch belongs to gym if we refer to it, though strictly not needed for constraints if FK valid
            
        elif user.role == 'gym_admin':
            form.instance.gym = user.gym
            
        if form.is_valid():
             config = form.save()
             messages.success(request, "Configuration added successfully.")
             return redirect('user-hik-config-list')
        else:
             messages.error(request, "Please correct the errors below.")
    else:
        form = HikConfigurationForm(user=user)
        
    context = {
        'form': form,
        'gym': user.gym if user.role == 'gym_admin' else (user.branch.gym if user.branch else None)
    }
    return render(request, "user/add_hik_config.html", context)


@login_required
def edit_hik_config(request, pk):
    user = request.user
    
    # Permission check for object access
    config = get_object_or_404(HikConfigurationDb, pk=pk)
    
    # Validate ownership
    has_permission = False
    if user.role == 'gym_admin' and user.gym:
        if config.gym == user.gym or (config.gym_branch and config.gym_branch.gym == user.gym):
            has_permission = True
    elif user.role == 'branch_admin' and user.branch:
        if config.gym_branch == user.branch:
            has_permission = True
            
    if not has_permission:
        messages.error(request, "You do not have permission to edit this configuration.")
        return redirect('user-hik-config-list')

    if request.method == 'POST':
        form = HikConfigurationForm(request.POST, instance=config, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuration updated successfully.")
            return redirect('user-hik-config-list')
    else:
        form = HikConfigurationForm(instance=config, user=user)
        
    context = {
        'form': form,
        'config': config,
         'gym': user.gym if user.role == 'gym_admin' else (user.branch.gym if user.branch else None)
    }
    return render(request, "user/add_hik_config.html", context)


@login_required
def delete_hik_config(request, pk):
    user = request.user
    
    if user.role == 'branch_admin':
         messages.error(request, "Branch Managers cannot delete configurations.")
         return redirect('user-hik-config-list')
         
    config = get_object_or_404(HikConfigurationDb, pk=pk)
    
    # Gym Admin check
    if user.role == 'gym_admin' and user.gym:
        if config.gym == user.gym or (config.gym_branch and config.gym_branch.gym == user.gym):
            config.delete()
            messages.success(request, "Configuration deleted successfully.")
        else:
             messages.error(request, "Permission denied.")
    else:
          messages.error(request, "Permission denied.")
          
    return redirect('user-hik-config-list')
