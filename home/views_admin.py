from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

#auth imports

from .models import CustomUser, GymOffice, GymBranch
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth.decorators import login_required


# self imports 

from .decorators import is_authenticated_user, admin_only
from notifications.models import Notification



# @is_authenticated_user
def signin(request):
    if request.user.is_authenticated:
        if request.user.role == "admin":
            return redirect("admin-dashboard")
        else:
            return redirect("user-dashboard")
    else:       
        if request.method == "POST":
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('admin-dashboard')
            else:
                messages.error(request, 'Invalid credentials')
    return render(request,"login.html")



def signout(request):
    logout(request)
    return redirect('signin')


@login_required
@admin_only
def admin_dashboard(request):
    # Fetch Counts
    gym_offices_count = GymOffice.objects.count()
    active_branches_count = GymBranch.objects.filter(is_active=True).count()
    users_count = CustomUser.objects.exclude(role='admin', is_superuser = True).count()
    
    # Recent Gym Offices
    recent_gyms = GymOffice.objects.order_by('-created_at')[:5]
    
    # Recent Notifications (Global for Super Admin)
    recent_notifications = Notification.objects.order_by('-created_at')[:10]
    unread_notifications_count = Notification.objects.filter(is_read=False).count()
    
    context = {
        'gym_offices_count': gym_offices_count,
        'active_branches_count': active_branches_count,
        'users_count': users_count,
        'recent_gyms': recent_gyms,
        'notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
    }
    return render(request, "admin/dashboard.html", context)



from .forms import GymOfficeForm, GymBranchForm, GymUserForm, GymOfficeCreationForm

@login_required
def gym_office_list(request):
    # Only show non-deleted gyms
    gym_offices = GymOffice.objects.filter(is_deleted=False).prefetch_related('gym_branches')
    return render(request, "admin/gym/gym_office_list.html", {'gym_offices': gym_offices})

@login_required
def add_gym_office(request):
    if request.method == 'POST':
        form = GymOfficeCreationForm(request.POST, request.FILES)
        if form.is_valid():
            # Save GymOffice (trial_ends_at is handled in model.save)
            gym = form.save()
            
            # Create CustomUser
            password = form.cleaned_data['password']
            email = form.cleaned_data['email'] 
            
            try:
                user = CustomUser.objects.create_user(
                    email=email,
                    password=password,
                    role='gym_admin',
                    gym=gym,
                    phone_number=gym.phone, # Use gym phone for user or let it be empty? Model says required.
                    is_active=True
                )
                messages.success(request, f"Gym '{gym.name}' and Admin User created successfully with 15 days trial.")
                return redirect('gym-office-list')
            except Exception as e:
                # If user creation fails, we might want to rollback gym creation or just warn.
                # For simplicity, we'll warn and maybe user can be added manually.
                messages.warning(request, f"Gym created but user creation failed: {str(e)}")
                return redirect('gym-office-detail', pk=gym.pk)
        else:
             messages.error(request, "Please correct the errors below.")
    else:
        form = GymOfficeCreationForm()
    
    return render(request, "admin/gym/add_gym_office.html", {'form': form})

@login_required
def gym_office_detail(request, pk):
    try:
        gym = GymOffice.objects.get(pk=pk, is_deleted=False)
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')
        
    branches = gym.gym_branches.filter(is_deleted=False)
    users = gym.users.filter(is_deleted=False)
    subscriptions = gym.subscription_history.filter(is_deleted=False).order_by('-created_at')
    payments = gym.payment_transactions.filter(is_deleted=False).order_by('-created_at')
    
    context = {
        'gym': gym,
        'branches': branches,
        'users': users,
        'subscriptions': subscriptions,
        'payments': payments,
    }
    return render(request, "admin/gym/gym_office_detail.html", context)

@login_required
def gym_office_edit(request, pk):
    try:
        gym = GymOffice.objects.get(pk=pk, is_deleted=False)
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')

    if request.method == 'POST':
        form = GymOfficeForm(request.POST, request.FILES, instance=gym)
        if form.is_valid():
            form.save()
            messages.success(request, f"Gym '{gym.name}' updated successfully.")
            return redirect('gym-office-detail', pk=pk)
    else:
        form = GymOfficeForm(instance=gym)
    
    return render(request, "admin/gym/gym_office_form.html", {'form': form, 'gym': gym})

@login_required
def add_gym_branch(request, gym_id):
    try:
        gym = GymOffice.objects.get(pk=gym_id, is_deleted=False)
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')
        
    if request.method == 'POST':
        form = GymBranchForm(request.POST)
        form.instance.gym = gym
        if form.is_valid():
            branch = form.save()
            messages.success(request, f"Branch '{branch.name}' added successfully.")
            return redirect('gym-office-detail', pk=gym_id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymBranchForm()
        
    return render(request, "admin/gym/add_branch_form.html", {'form': form, 'gym': gym})

@login_required
def add_gym_user(request, gym_id):
    try:
        gym = GymOffice.objects.get(pk=gym_id, is_deleted=False)
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')
        
    if request.method == 'POST':
        form = GymUserForm(request.POST, gym=gym)
        form.instance.gym = gym
        if form.is_valid():
            user = form.save()
            messages.success(request, f"User '{user.get_full_name()}' added successfully.")
            return redirect('gym-office-detail', pk=gym_id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = GymUserForm(gym=gym)
        
    return render(request, "admin/gym/add_user_form.html", {'form': form, 'gym': gym})

@login_required
def gym_office_delete(request, pk):
    if request.method == "POST":
        try:
            gym = GymOffice.objects.get(pk=pk, is_deleted=False)
            gym.soft_delete()
            messages.success(request, f"Gym '{gym.name}' has been deleted successfully.")
        except GymOffice.DoesNotExist:
            messages.error(request, "Gym Office not found.")
    return redirect('gym-office-list')


from .forms import LicenseKeyForm
from .models import LicenseKey

@login_required
def add_license_key(request, gym_id):
    try:
        gym = GymOffice.objects.get(pk=gym_id, is_deleted=False)
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')
    
    if gym.license_key:
        messages.warning(request, "This gym already has a license key assigned. You can edit it instead.")
        return redirect('gym-office-detail', pk=gym_id)

    if request.method == 'POST':
        form = LicenseKeyForm(request.POST)
        if form.is_valid():
            license_key = form.save(commit=False)
            license_key.assigned_to = gym
            license_key.save()
            
            gym.license_key = license_key
            gym.save()
            
            messages.success(request, f"License key generated and assigned successfully.")
            return redirect('gym-office-detail', pk=gym_id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Default defaults
        initial_data = {
            'valid_until': timezone.now().date() + timedelta(days=365),
            'fetcher_attendance': True,
            'fetcher_payment': True,
            'max_staff': 5
        }
        form = LicenseKeyForm(initial=initial_data)
        
    return render(request, "admin/gym/license_form.html", {
        'form': form, 
        'gym': gym,
        'title': 'Generate License Key'
    })

@login_required
def edit_license_key(request, gym_id):
    try:
        gym = GymOffice.objects.get(pk=gym_id, is_deleted=False)
        if not gym.license_key:
             messages.error(request, "No license key found for this gym.")
             return redirect('gym-office-detail', pk=gym_id)
        license_key = gym.license_key
    except GymOffice.DoesNotExist:
        messages.error(request, "Gym Office not found.")
        return redirect('gym-office-list')

    if request.method == 'POST':
        form = LicenseKeyForm(request.POST, instance=license_key)
        if form.is_valid():
            form.save()
            messages.success(request, "License key updated successfully.")
            return redirect('gym-office-detail', pk=gym_id)
        else:
             messages.error(request, "Please correct the errors below.")
    else:
        form = LicenseKeyForm(instance=license_key)
    
    return render(request, "admin/gym/license_form.html", {
        'form': form, 
        'gym': gym,
        'title': 'Edit License Key'
    })

@login_required
def delete_license_key(request, gym_id):
    if request.method == "POST":
        try:
            gym = GymOffice.objects.get(pk=gym_id, is_deleted=False)
            if gym.license_key:
                license_key = gym.license_key
                # Soft delete license
                license_key.soft_delete()
                
                # Unassign from gym
                gym.license_key = None
                gym.save()
                
                messages.success(request, "License key deleted and removed from gym.")
            else:
                messages.error(request, "No license key to delete.")
        except GymOffice.DoesNotExist:
            messages.error(request, "Gym Office not found.")
            
    return redirect('gym-office-detail', pk=gym_id)