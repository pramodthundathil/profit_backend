from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

LICENSE_EXPIRED = 'LICENSE_EXPIRED'

# Roles whose access depends on the gym's platform subscription.
GATED_ROLES = ('gym_admin', 'branch_admin', 'staff', 'trainer')

# Reachable without a subscription, so the app can show the recharge screen.
EXEMPT_PATHS = (
    '/auth/users/users/me/',
    '/auth/users/subscription/status/',
)


def has_platform_access(user):
    """True unless a gym user's gym has no active trial, subscription or license."""
    if user.is_superuser or user.role not in GATED_ROLES:
        return True
    return bool(user.gym and user.gym.can_access_service())


class SubscriptionJWTAuthentication(JWTAuthentication):
    """JWT authentication that rejects users of gyms without a subscription.

    LicenseValidationMiddleware cannot do this for the mobile app: it runs before
    DRF reads the token, so JWT users are still anonymous there.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None or request.path_info in EXEMPT_PATHS:
            return result
        if not has_platform_access(result[0]):
            raise PermissionDenied({
                'code': LICENSE_EXPIRED,
                'detail': 'Your subscription has expired. Please renew to continue using the service.',
            })
        return result
