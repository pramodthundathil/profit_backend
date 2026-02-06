from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import GymOffice, CustomUser, PaymentTransaction, SubscriptionHistory, HikConfigurationDb, GymBranch

from .forms import GymBranchForm, GymUserForm, HikConfigurationForm, GymUserEditForm


@login_required
def user_dashboard(request):
    user = request.user
    
    context = {}
    
    if user.gym:
        gym = user.gym
        context['gym'] = gym
        # Fetch data related to the gym
        context['branches'] = gym.gym_branches.filter(is_deleted=False)
        context['members'] = gym.users.filter(is_deleted=False).exclude(id=user.id) # Show other staff
        context['subscriptions'] = gym.subscription_history.filter(is_deleted=False).order_by('-created_at')
        context['payments'] = gym.payment_transactions.filter(is_deleted=False).order_by('-created_at')
        
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
        'gym': user.gym if user.role == 'gym_admin' else user.branch.gym
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
        'gym': user.gym if user.role == 'gym_admin' else user.branch.gym
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
         'gym': user.gym if user.role == 'gym_admin' else getattr(user.branch, 'gym', None)
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
