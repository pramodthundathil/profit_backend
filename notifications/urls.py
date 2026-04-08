from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, notification_list_web, mark_notification_as_read, mark_all_notifications_as_read

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = [
    path('api/', include(router.urls)),
    
    # Web Routes
    path('list/', notification_list_web, name='notification-list'),
    path('mark-read/<int:pk>/', mark_notification_as_read, name='notification-mark-read'),
    path('mark-all-read/', mark_all_notifications_as_read, name='notification-mark-all-read'),
]
