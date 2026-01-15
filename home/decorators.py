from django.shortcuts import redirect 


def is_authenticated_user(view_func):
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role == "admin":
                return redirect("admin-dashboard")
            else:
                pass 
        else:
            return view_func(request, *args, **kwargs)
        
    return wrapper_func

def admin_only(view_func):
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role == "admin":
                return view_func(request, *args, **kwargs)
            else:
                return redirect("user-dashboard")
        else:
            return redirect("signin")
        
    return wrapper_func