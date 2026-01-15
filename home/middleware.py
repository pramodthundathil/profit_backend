from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib import messages
from django.http import JsonResponse
import re

class LicenseValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/admin/', 
            '/static/', 
            '/media/', 
            # '/auth/', # REMOVED: Too broad, allows dashboard access
            '/favicon.ico'
        ]


    def __call__(self, request):
        # 1. Skip if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 2. Skip for Super Admins
        if request.user.role == 'admin' or request.user.is_superuser:
            return self.get_response(request)

        # 3. Skip exempt paths
        path = request.path_info
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return self.get_response(request)
            
        # 4. Skip Login/Logout/Signout, and the Subscription Expired page itself
        # resolving URLs to avoid hardcoding issues if names change, but keeping strings for safety
        if path in [
            reverse('signin'), 
            reverse('signout'), 
            '/auth/login/', # Specific API Login
            '/auth/refresh/', # Specific API Refresh
            reverse('subscription_expired')
        ]:

            return self.get_response(request)

        # 5. Allow access to Payment APIs/Views so they can renew
        # Assuming payment URLs contain 'payment' or 'subscription'
        if 'payment' in path or 'subscription' in path:
             # But prevent dashboard access if it falls under this rule accidentally (unlikely but safe)
             if 'dashboard' not in path:
                 return self.get_response(request)

        # 6. Check Gym Access
        gym = request.user.gym
        if gym and not gym.can_access_service():
            
            # Determine if it's an API request or Web request
            is_api = (
                request.headers.get('Accept') == 'application/json' or 
                path.startswith('/api/') or 
                path.startswith('/v1/') or 
                path.startswith('/v2/') 
                # path.startswith('/auth/') 
            )

            if is_api:
                return JsonResponse({
                    'code': 'LICENSE_EXPIRED',
                    'detail': 'Your gym\'s license or trial period has expired. Please contact your administrator to renew.'
                }, status=403)
            else:
                # For Web Users
                # Only redirect if not already there (checked in step 4, but double check)
                if path != reverse('subscription_expired'):
                     # Option: Logout the user so they are forced to see the issue? 
                     # Or keep them logged in but trapped?
                     # Plan said: "Trapped" in subscription expired page.
                     return redirect('subscription_expired')

        return self.get_response(request)
