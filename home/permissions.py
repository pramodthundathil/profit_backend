from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """
    Permission class for super admin only
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class IsGymAdmin(permissions.BasePermission):
    """
    Permission class for gym admin
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'gym_admin']


class IsBranchAdmin(permissions.BasePermission):
    """
    Permission class for branch admin
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'gym_admin', 'branch_admin']


class IsGymAdminOrReadOnly(permissions.BasePermission):
    """
    Allow gym admin to edit, others to read only
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'gym_admin']


class CanManageGym(permissions.BasePermission):
    """
    Check if user can manage specific gym
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can manage all gyms
        if user.role == 'admin':
            return True
        
        # Gym admin can manage only their gym
        if user.role == 'gym_admin':
            # Handle different object types
            if hasattr(obj, 'gym'):  # For users, branches
                return obj.gym == user.gym
            else:  # For gym office itself
                return obj == user.gym
        
        return False


class CanManageBranch(permissions.BasePermission):
    """
    Check if user can manage specific branch
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can manage all branches
        if user.role == 'admin':
            return True
        
        # Gym admin can manage all branches in their gym
        if user.role == 'gym_admin':
            if hasattr(obj, 'branch'):  # For users in branch
                return obj.branch.gym == user.gym if obj.branch else False
            else:  # For branch itself
                return obj.gym == user.gym
        
        # Branch admin can manage only their branch
        if user.role == 'branch_admin':
            if hasattr(obj, 'branch'):  # For users in branch
                return obj.branch == user.branch
            else:  # For branch itself
                return obj == user.branch
        
        return False


class CanCreateBranch(permissions.BasePermission):
    """
    Check if gym can create new branches based on license
    """
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # Super admin can always create
        if user.role == 'admin':
            return True
        
        # Gym admin can create if their gym has permission
        if user.role == 'gym_admin' and user.gym:
            return user.gym.can_create_branch()
        
        return False


class CanManageUsers(permissions.BasePermission):
    """
    Check if user can manage other users
    """
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # Admin, gym_admin, and branch_admin can manage users
        return user.role in ['admin', 'gym_admin', 'branch_admin']
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can manage all users
        if user.role == 'admin':
            return True
        
        # Gym admin can manage users in their gym
        if user.role == 'gym_admin':
            return obj.gym == user.gym
        
        # Branch admin can manage users in their branch
        if user.role == 'branch_admin':
            return obj.branch == user.branch
        
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners to edit
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions only for owner
        return obj == request.user


class HasActiveSubscription(permissions.BasePermission):
    """
    Check if gym has active subscription or trial
    """
    message = "Your subscription has expired. Please renew to continue using the service."
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # Super admin always has access
        if user.role == 'admin':
            return True
        
        # Check if user's gym has active subscription
        if user.gym:
            return user.gym.can_access_service()
        
        return False


class CanAccessFeature(permissions.BasePermission):
    """
    Check if gym's license has access to specific feature
    Usage: Add feature_name to view
    Example: feature_name = 'multi_branch'
    """
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # Super admin always has access
        if user.role == 'admin':
            return True
        
        # Get feature name from view
        feature_name = getattr(view, 'feature_name', None)
        
        if not feature_name:
            return True  # No feature restriction
        
        # Check if user's gym has the feature
        if user.gym and user.gym.license_key:
            return user.gym.license_key.has_feature(feature_name)
        
        return False


class IsSameGymOrAdmin(permissions.BasePermission):
    """
    Check if users belong to same gym or user is admin
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can access everything
        if user.role == 'admin':
            return True
        
        # Check if same gym
        if hasattr(obj, 'gym'):
            return obj.gym == user.gym
        
        return False


class CanViewBranch(permissions.BasePermission):
    """
    Check if user can view branch details
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Super admin can view all
        if user.role == 'admin':
            return True
        
        # Gym admin can view all branches in their gym
        if user.role == 'gym_admin':
            return obj.gym == user.gym
        
        # Others can view only their branch
        return obj == user.branch

