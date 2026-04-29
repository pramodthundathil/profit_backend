from django.urls import path
from .views import (
    SendEmailOTPView, VerifyEmailOTPView, 
    EmailPasswordLoginView, SetPasswordView,
    MemberProfileView
)

urlpatterns = [
    path('auth/send-otp/', SendEmailOTPView.as_view(), name='member-send-otp'),
    path('auth/verify-otp/', VerifyEmailOTPView.as_view(), name='member-verify-otp'),
    path('auth/login/', EmailPasswordLoginView.as_view(), name='member-login'),
    path('auth/set-password/', SetPasswordView.as_view(), name='member-set-password'),
    path('profile/', MemberProfileView.as_view(), name='member-profile'),
]
