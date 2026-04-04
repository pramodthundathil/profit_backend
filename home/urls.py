from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    GymRegistrationView, GymOfficeViewSet, GymBranchViewSet,
    CustomUserViewSet, LicenseKeyViewSet, SubscriptionHistoryViewSet,
    PaymentTransactionViewSet, DashboardStatsView, HikConfigurationDbViewSet,
    CustomTokenObtainPairView
)

from .import views_admin, views_user

router = DefaultRouter()
router.register(r'gyms', GymOfficeViewSet, basename='gym')
router.register(r'branches', GymBranchViewSet, basename='branch')
router.register(r'users', CustomUserViewSet, basename='user')
router.register(r'licenses', LicenseKeyViewSet, basename='license')
router.register(r'subscriptions', SubscriptionHistoryViewSet, basename='subscription')
router.register(r'payments', PaymentTransactionViewSet, basename='payment')
router.register(r'hik-configs', HikConfigurationDbViewSet, basename='hik-config')

urlpatterns = [
    # Public registration endpoint
    path('register/', GymRegistrationView.as_view(), name='gym-registration'),
    
    # JWT Authentication
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Dashboard stats
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    
    # Router URLs
    path('', include(router.urls)),

    #user dashboard
    path('user/dashboard/', views_user.user_dashboard, name='user-dashboard'),
    path('user/branches/', views_user.branch_list, name='user-branch-list'),
    path('user/branches/<int:pk>/edit/', views_user.edit_branch, name='user-edit-branch'),
    path('user/branches/<int:pk>/delete/', views_user.delete_branch, name='user-delete-branch'),
    path('user/staff/', views_user.staff_list, name='user-staff-list'),
    path('user/staff/<int:pk>/edit/', views_user.edit_staff, name='user-edit-staff'),
    path('user/staff/<int:pk>/delete/', views_user.delete_staff, name='user-delete-staff'),
    path('user/add-branch/', views_user.add_branch, name='user-add-branch'),
    path('user/add-staff/', views_user.add_staff, name='user-add-staff'),
    path('subscription-expired/', views_user.subscription_expired, name='subscription_expired'),
    
    # Hik Settings
    path('user/settings/hik/', views_user.hik_config_list, name='user-hik-config-list'),
    path('user/settings/hik/add/', views_user.add_hik_config, name='user-add-hik-config'),
    path('user/settings/hik/<int:pk>/edit/', views_user.edit_hik_config, name='user-edit-hik-config'),
    path('user/settings/hik/<int:pk>/delete/', views_user.delete_hik_config, name='user-delete-hik-config'),

    # Gym Configuration




    # admin dashboard urls
    path('dashboard/', views_admin.admin_dashboard, name='admin-dashboard'),
    path("signout",views_admin.signout,name="signout"),

    path('dashboard/gym-office-list/', views_admin.gym_office_list, name='gym-office-list'),
    path('dashboard/add-gym-office/', views_admin.add_gym_office, name='add-gym-office'),
    path('dashboard/gym-office/<int:pk>/', views_admin.gym_office_detail, name='gym-office-detail'),
    path('dashboard/gym-office/<int:pk>/edit/', views_admin.gym_office_edit, name='gym-office-edit'),
    path('dashboard/gym-office/<int:gym_id>/add-branch/', views_admin.add_gym_branch, name='add-gym-branch'),
    path('dashboard/gym-office/<int:gym_id>/add-user/', views_admin.add_gym_user, name='add-gym-user'),
    path('dashboard/gym-office/<int:gym_id>/add-license/', views_admin.add_license_key, name='add-license-key'),
    path('dashboard/gym-office/<int:gym_id>/edit-license/', views_admin.edit_license_key, name='edit-license-key'),
    path('dashboard/gym-office/<int:gym_id>/delete-license/', views_admin.delete_license_key, name='delete-license-key'),
    path('dashboard/gym-office/<int:pk>/delete/', views_admin.gym_office_delete, name='gym-office-delete'),
]