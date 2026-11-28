from django.urls import path

from . import admin_views, views_web
from .views import (
    EmailPasswordLoginView, LogoutView, MemberAppConfigView, MemberProfileView,
    SendEmailOTPView, SetPasswordView, VerifyEmailOTPView,
)

urlpatterns = [
    # Member app
    path('auth/login/', EmailPasswordLoginView.as_view(), name='member-login'),
    path('auth/logout/', LogoutView.as_view(), name='member-logout'),
    path('auth/send-otp/', SendEmailOTPView.as_view(), name='member-send-otp'),
    path('auth/verify-otp/', VerifyEmailOTPView.as_view(), name='member-verify-otp'),
    path('auth/change-password/', SetPasswordView.as_view(), name='member-change-password'),
    path('auth/set-password/', SetPasswordView.as_view(), name='member-set-password'),  # older app versions
    path('config/', MemberAppConfigView.as_view(), name='member-app-config'),
    path('profile/', MemberProfileView.as_view(), name='member-profile'),

    # Gym staff (Profit_app)
    path('admin/settings/', admin_views.MemberAppSettingsView.as_view(), name='member-app-admin-settings'),
    path('admin/members/<int:pk>/login/', admin_views.MemberLoginStatusView.as_view(), name='member-app-admin-login-status'),
    path('admin/members/<int:pk>/login/enable/', admin_views.MemberEnableLoginView.as_view(), name='member-app-admin-login-enable'),
    path('admin/members/<int:pk>/login/resend/', admin_views.MemberResendCredentialsView.as_view(), name='member-app-admin-login-resend'),
    path('admin/members/<int:pk>/login/disable/', admin_views.MemberDisableLoginView.as_view(), name='member-app-admin-login-disable'),
    path('admin/members/login/bulk-enable/', admin_views.BulkEnableLoginView.as_view(), name='member-app-admin-login-bulk'),

    # Web console pages
    path('web/settings/', views_web.member_app_settings, name='member-app-settings'),
    path('web/settings/bulk-enable/', views_web.member_app_bulk_enable, name='member-app-bulk-enable'),
]
