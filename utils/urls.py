from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BatchViewSet, TypeSubscriptionViewSet, SubscriptionPeriodViewSet,
    AdminBatchViewSet, AdminTypeSubscriptionViewSet, AdminSubscriptionPeriodViewSet
)
from . import views_user

router = DefaultRouter()

# Gym/User Routes
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'subscription-types', TypeSubscriptionViewSet, basename='subtype')
router.register(r'subscription-periods', SubscriptionPeriodViewSet, basename='subperiod')

# Super Admin Routes
router.register(r'admin/batches', AdminBatchViewSet, basename='admin-batch')
router.register(r'admin/subscription-types', AdminTypeSubscriptionViewSet, basename='admin-subtype')
router.register(r'admin/subscription-periods', AdminSubscriptionPeriodViewSet, basename='admin-subperiod')

urlpatterns = [
    path('', include(router.urls)),
    
    # Gym Configuration (HTML)
    path('user/configuration/', views_user.gym_config_list, name='gym-config-list'),
    path('user/configuration/settings/update/', views_user.update_gym_settings, name='update-gym-settings'),
    
    # Batches
    path('user/configuration/batch/add/', views_user.batch_create, name='batch-create'),
    path('user/configuration/batch/<int:pk>/edit/', views_user.batch_edit, name='batch-edit'),
    path('user/configuration/batch/<int:pk>/delete/', views_user.batch_delete, name='batch-delete'),
    
    # Subscription Types
    path('user/configuration/subtype/add/', views_user.subtype_create, name='subtype-create'),
    path('user/configuration/subtype/<int:pk>/edit/', views_user.subtype_edit, name='subtype-edit'),
    path('user/configuration/subtype/<int:pk>/delete/', views_user.subtype_delete, name='subtype-delete'),
    
    # Subscription Periods
    path('user/configuration/subperiod/add/', views_user.subperiod_create, name='subperiod-create'),
    path('user/configuration/subperiod/<int:pk>/edit/', views_user.subperiod_edit, name='subperiod-edit'),
    path('user/configuration/subperiod/<int:pk>/delete/', views_user.subperiod_delete, name='subperiod-delete'),
]
