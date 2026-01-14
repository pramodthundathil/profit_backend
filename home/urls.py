from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    GymRegistrationView, GymOfficeViewSet, GymBranchViewSet,
    CustomUserViewSet, LicenseKeyViewSet, SubscriptionHistoryViewSet,
    PaymentTransactionViewSet, DashboardStatsView
)

from .import views_admin

router = DefaultRouter()
router.register(r'gyms', GymOfficeViewSet, basename='gym')
router.register(r'branches', GymBranchViewSet, basename='branch')
router.register(r'users', CustomUserViewSet, basename='user')
router.register(r'licenses', LicenseKeyViewSet, basename='license')
router.register(r'subscriptions', SubscriptionHistoryViewSet, basename='subscription')
router.register(r'payments', PaymentTransactionViewSet, basename='payment')

urlpatterns = [
    # Public registration endpoint
    path('register/', GymRegistrationView.as_view(), name='gym-registration'),
    
    # JWT Authentication
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Dashboard stats
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    
    # Router URLs
    path('', include(router.urls)),



    # admin dashboard urls
    path('dashboard/', views_admin.admin_dashboard, name='admin-dashboard'),
]