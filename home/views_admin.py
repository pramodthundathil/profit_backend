from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages

#auth imports

from .models import CustomUser, GymOffice, GymBranch
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth.decorators import login_required



def signin(request):
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


@login_required
def admin_dashboard(request):
    # Fetch Counts
    gym_offices_count = GymOffice.objects.count()
    active_branches_count = GymBranch.objects.filter(is_active=True).count()
    users_count = CustomUser.objects.exclude(role='admin', is_superuser = True).count()
    
    # Recent Gym Offices
    recent_gyms = GymOffice.objects.order_by('-created_at')[:5]
    
    context = {
        'gym_offices_count': gym_offices_count,
        'active_branches_count': active_branches_count,
        'users_count': users_count,
        'recent_gyms': recent_gyms,
    }
    return render(request, "admin/dashboard.html", context)