from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import GymOffice, CustomUser, PaymentTransaction, SubscriptionHistory
from .forms import GymBranchForm, GymUserForm

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
        
    context = {
        'gym': user.gym,
        'branches': user.gym.gym_branches.filter(is_deleted=False)
    }
    return render(request, "user/branch_list.html", context)

@login_required
def staff_list(request):
    user = request.user
    if not user.gym:
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
