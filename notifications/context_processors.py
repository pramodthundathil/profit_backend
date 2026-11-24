import os

from django.contrib.staticfiles import finders

from home.platform_alerts import get_platform_alerts
from .models import Notification

def _admin_css_version():
    """File mtime, so browsers fetch the stylesheet again whenever it changes."""
    path = finders.find('css/admin_dashboard.css')
    return int(os.path.getmtime(path)) if path else 0

def notifications_processor(request):
    if not request.user.is_authenticated:
        return {}

    if request.user.role == 'admin':
        # Super Admin gets gym expiry/recharge alerts, not member notifications
        return {
            'platform_alerts': get_platform_alerts(request),
            'admin_css_version': _admin_css_version(),
            'notifications': [],
            'unread_notifications_count': 0,
        }

    if request.user.gym:
        # Gym Admin sees their gym's members' notifications
        qs = Notification.objects.filter(member__gym=request.user.gym)
        return {
            'notifications': qs.order_by('-created_at')[:10],
            'unread_notifications_count': qs.filter(is_read=False).count(),
        }

    return {'notifications': [], 'unread_notifications_count': 0}
