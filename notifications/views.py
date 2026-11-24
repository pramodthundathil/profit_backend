from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from home.platform_alerts import get_platform_alerts
from .models import Notification
from .serializers import NotificationSerializer
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Notification.objects.none()
            
        if user.role == 'admin':
            # Super Admin sees everything
            return Notification.objects.all()
        elif user.role == 'gym_admin' and user.gym:
            # Gym Admin sees only their gym's notifications
            return Notification.objects.filter(member__gym=user.gym)
        elif user.role in ['branch_admin', 'staff', 'trainer'] and user.gym:
             # Staff see their gym's notifications (or branch specific)
             if user.branch:
                 return Notification.objects.filter(member__branch=user.branch)
             return Notification.objects.filter(member__gym=user.gym)
        else:
            # Regular members see only their own
            return Notification.objects.filter(member_email=user.email)

    @action(detail=True, methods=['patch'])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'notification marked as read'})

    @action(detail=False, methods=['patch'])
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'status': 'all notifications marked as read'})

# --- Web Interface Views ---

def _web_notifications(user):
    """Member notifications the user may manage on the web: own gym only.

    Do not use user.is_staff here: gym and branch admins are is_staff too.
    The super admin works with platform alerts instead (home.platform_alerts).
    """
    if user.role != 'admin' and user.gym:
        return Notification.objects.filter(member__gym=user.gym)
    return Notification.objects.none()

@login_required
def notification_list_web(request):
    user = request.user
    if user.role == 'admin':
        alerts = get_platform_alerts(request)
        category = request.GET.get('type')
        if category not in ('expiry', 'recharge'):
            category = 'all'
        return render(request, "admin/alerts.html", {
            'alerts': alerts[category],
            'category': category,
        })

    return render(request, "notifications/list.html", {
        'all_notifications': _web_notifications(user).order_by('-created_at'),
        'title': 'Notification History'
    })

@login_required
@require_POST
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(_web_notifications(request.user), pk=pk)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def mark_all_notifications_as_read(request):
    _web_notifications(request.user).filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def delete_notification(request, pk):
    get_object_or_404(_web_notifications(request.user), pk=pk).delete()
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def clear_all_notifications(request):
    _web_notifications(request.user).delete()
    return JsonResponse({'status': 'success'})
