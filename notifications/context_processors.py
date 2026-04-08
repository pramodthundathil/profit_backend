from .models import Notification

def notifications_processor(request):
    if request.user.is_authenticated:
        if request.user.role == 'admin':
            # Super Admin sees everything
            notifications = Notification.objects.order_by('-created_at')[:10]
            unread_count = Notification.objects.filter(is_read=False).count()
        elif request.user.gym:
            # Gym Admin sees their gym's members' notifications
            notifications = Notification.objects.filter(member__gym=request.user.gym).order_by('-created_at')[:10]
            unread_count = Notification.objects.filter(member__gym=request.user.gym, is_read=False).count()
        else:
            notifications = []
            unread_count = 0
            
        return {
            'notifications': notifications,
            'unread_notifications_count': unread_count
        }
    return {}
