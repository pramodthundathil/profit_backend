from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from utils.models import Batch_DB, TypeSubscription, SubscriptionPeriod
from utils.forms import BatchForm, TypeSubscriptionForm, SubscriptionPeriodForm
from home.forms import GymOfficeSettingsForm

@login_required
def gym_config_list(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied. No gym associated.")
        return redirect('user-dashboard')

    gym = user.gym
    
    batches = Batch_DB.objects.filter(gym=gym)
    sub_types = TypeSubscription.objects.filter(gym=gym)
    sub_periods = SubscriptionPeriod.objects.filter(gym=gym)
    
    context = {
        'gym': gym,
        'batches': batches,
        'sub_types': sub_types,
        'sub_periods': sub_periods,
        'settings_form': GymOfficeSettingsForm(instance=gym),
    }
    return render(request, "user/configuration/gym_config_list.html", context)

# --- Batches ---

@login_required
def batch_create(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')
        
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.gym = user.gym
            try:
                batch.save()
                messages.success(request, f"Batch '{batch.batch_name}' created successfully.")
                return redirect('gym-config-list')
            except Exception as e:
                messages.error(request, f"Error creating batch: {e}")
    else:
        form = BatchForm()
        
    return render(request, "user/configuration/batch_form.html", {'form': form, 'title': 'Create Batch'})

@login_required
def batch_edit(request, pk):
    user = request.user
    batch = get_object_or_404(Batch_DB, pk=pk)
    
    if user.role != 'gym_admin' or batch.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
         
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, "Batch updated successfully.")
            return redirect('gym-config-list')
    else:
        form = BatchForm(instance=batch)
        
    return render(request, "user/configuration/batch_form.html", {'form': form, 'title': 'Edit Batch'})

@login_required
def batch_delete(request, pk):
    user = request.user
    batch = get_object_or_404(Batch_DB, pk=pk)
    
    if user.role != 'gym_admin' or batch.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
    
    if request.method == 'POST':
        batch.delete()
        messages.success(request, "Batch deleted successfully.")
        
    return redirect('gym-config-list')

# --- Subscription Types ---

@login_required
def subtype_create(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')
        
    if request.method == 'POST':
        form = TypeSubscriptionForm(request.POST)
        if form.is_valid():
            subtype = form.save(commit=False)
            subtype.gym = user.gym
            try:
                subtype.save()
                messages.success(request, f"Subscription Type '{subtype.name}' created successfully.")
                return redirect('gym-config-list')
            except Exception as e:
                 messages.error(request, f"Error: {e}")
    else:
        form = TypeSubscriptionForm()
        
    return render(request, "user/configuration/subtype_form.html", {'form': form, 'title': 'Create Subscription Type'})

@login_required
def subtype_edit(request, pk):
    user = request.user
    subtype = get_object_or_404(TypeSubscription, pk=pk)
    
    if user.role != 'gym_admin' or subtype.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
         
    if request.method == 'POST':
        form = TypeSubscriptionForm(request.POST, instance=subtype)
        if form.is_valid():
            form.save()
            messages.success(request, "Subscription Type updated successfully.")
            return redirect('gym-config-list')
    else:
        form = TypeSubscriptionForm(instance=subtype)
        
    return render(request, "user/configuration/subtype_form.html", {'form': form, 'title': 'Edit Subscription Type'})

@login_required
def subtype_delete(request, pk):
    user = request.user
    subtype = get_object_or_404(TypeSubscription, pk=pk)
    
    if user.role != 'gym_admin' or subtype.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
    
    if request.method == 'POST':
        subtype.delete()
        messages.success(request, "Subscription Type deleted successfully.")
        
    return redirect('gym-config-list')

# --- Subscription Periods ---

@login_required
def subperiod_create(request):
    user = request.user
    if not user.gym:
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')
        
    if request.method == 'POST':
        form = SubscriptionPeriodForm(request.POST)
        if form.is_valid():
            subperiod = form.save(commit=False)
            subperiod.gym = user.gym
            try:
                subperiod.save()
                messages.success(request, f"Subscription Period '{subperiod.period} days' created successfully.")
                return redirect('gym-config-list')
            except Exception as e:
                messages.error(request, f"Error: {e}")
    else:
        form = SubscriptionPeriodForm()
        
    return render(request, "user/configuration/subperiod_form.html", {'form': form, 'title': 'Create Subscription Period'})

@login_required
def subperiod_edit(request, pk):
    user = request.user
    subperiod = get_object_or_404(SubscriptionPeriod, pk=pk)
    
    if user.role != 'gym_admin' or subperiod.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
         
    if request.method == 'POST':
        form = SubscriptionPeriodForm(request.POST, instance=subperiod)
        if form.is_valid():
            form.save()
            messages.success(request, "Subscription Period updated successfully.")
            return redirect('gym-config-list')
    else:
        form = SubscriptionPeriodForm(instance=subperiod)
        
    return render(request, "user/configuration/subperiod_form.html", {'form': form, 'title': 'Edit Subscription Period'})

@login_required
def subperiod_delete(request, pk):
    user = request.user
    subperiod = get_object_or_404(SubscriptionPeriod, pk=pk)
    
    if user.role != 'gym_admin' or subperiod.gym != user.gym:
         messages.error(request, "Access denied.")
         return redirect('user-dashboard')
    
    if request.method == 'POST':
        subperiod.delete()
        messages.success(request, "Subscription Period deleted successfully.")
        
    return redirect('gym-config-list')

@login_required
def update_gym_settings(request):
    user = request.user
    if user.role != 'gym_admin' or not user.gym:
        messages.error(request, "Access denied.")
        return redirect('user-dashboard')
        
    gym = user.gym
    if request.method == 'POST':
        form = GymOfficeSettingsForm(request.POST, instance=gym)
        if form.is_valid():
            form.save()
            messages.success(request, "Gym settings updated successfully.")
        else:
            messages.error(request, "Error updating settings. Please check the form.")
            
    return redirect('gym-config-list')
