from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
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

@login_required
def notification_list_web(request):
    user = request.user
    if user.is_staff:
        # Super Admin - see all notifications
        notifications = Notification.objects.all().order_by('-created_at')
    elif user.gym:
        # Gym Admin - see gym's notifications
        notifications = Notification.objects.filter(member__gym=user.gym).order_by('-created_at')
    else:
        notifications = Notification.objects.none()
        
    return render(request, "notifications/list.html", {
        'all_notifications': notifications,
        'title': 'Notification History'
    })

@login_required
@require_POST
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    
    # Simple permissions check
    if not request.user.is_staff:
        # Ensure the notification belongs to the user's gym
        if not notification.member.gym == request.user.gym:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
            
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def mark_all_notifications_as_read(request):
    user = request.user
    if user.is_staff:
        Notification.objects.filter(is_read=False).update(is_read=True)
    elif user.gym:
        Notification.objects.filter(member__gym=user.gym, is_read=False).update(is_read=True)
    
    return JsonResponse({'status': 'success'})
