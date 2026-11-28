from django.urls import path

from community import moderation, views as community
from . import admin_views, coach_views, health_forms, member_coaching_views as mc, views_web
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
    path('forms/', health_forms.HealthFormListView.as_view(), name='member-health-forms'),
    path('forms/<str:key>/', health_forms.HealthFormView.as_view(), name='member-health-form'),
    path('food-logs/', mc.MemberFoodLogListView.as_view(), name='member-food-logs'),
    path('food-logs/history/', mc.MemberFoodHistoryView.as_view(), name='member-food-history'),
    path('food-logs/<int:pk>/', mc.MemberFoodLogDetailView.as_view(), name='member-food-log'),
    path('instructions/', mc.MemberInstructionsView.as_view(), name='member-instructions'),
    path('instructions/<int:pk>/', mc.MemberInstructionDetailView.as_view(), name='member-instruction'),
    path('instructions/<int:pk>/comments/', mc.MemberInstructionCommentView.as_view(), name='member-instruction-comments'),
    path('instructions/<int:pk>/workout-log/', mc.MemberWorkoutLogView.as_view(), name='member-workout-log'),
    path('community/feed/', community.FeedView.as_view(), name='community-feed'),
    path('community/posts/', community.PostCreateView.as_view(), name='community-post-create'),
    path('community/posts/<int:pk>/', community.PostDetailView.as_view(), name='community-post'),
    path('community/posts/<int:pk>/like/', community.PostLikeView.as_view(), name='community-post-like'),
    path('community/posts/<int:pk>/comments/', community.PostCommentView.as_view(), name='community-post-comments'),
    path('community/posts/<int:pk>/report/', community.PostReportView.as_view(), name='community-post-report'),
    path('community/comments/<int:pk>/', community.CommentDeleteView.as_view(), name='community-comment'),
    path('community/me/', community.MyProfileView.as_view(), name='community-me'),
    path('community/profiles/<int:pk>/', community.ProfileView.as_view(), name='community-profile'),
    path('community/profiles/<int:pk>/block/', community.BlockView.as_view(), name='community-block'),

    # Gym staff (Profit_app)
    path('admin/settings/', admin_views.MemberAppSettingsView.as_view(), name='member-app-admin-settings'),
    path('admin/members/<int:pk>/login/', admin_views.MemberLoginStatusView.as_view(), name='member-app-admin-login-status'),
    path('admin/members/<int:pk>/login/enable/', admin_views.MemberEnableLoginView.as_view(), name='member-app-admin-login-enable'),
    path('admin/members/<int:pk>/login/resend/', admin_views.MemberResendCredentialsView.as_view(), name='member-app-admin-login-resend'),
    path('admin/members/<int:pk>/login/disable/', admin_views.MemberDisableLoginView.as_view(), name='member-app-admin-login-disable'),
    path('admin/members/login/bulk-enable/', admin_views.BulkEnableLoginView.as_view(), name='member-app-admin-login-bulk'),

    # Trainers and admins coaching members (Profit_app)
    path('coach/members/', coach_views.CoachMembersView.as_view(), name='coach-members'),
    path('coach/members/<int:pk>/', coach_views.CoachMemberOverviewView.as_view(), name='coach-member'),
    path('coach/members/<int:pk>/food-logs/', coach_views.CoachFoodLogsView.as_view(), name='coach-food-logs'),
    path('coach/members/<int:pk>/instructions/', coach_views.CoachInstructionListView.as_view(), name='coach-instructions'),
    path('coach/food-logs/<int:log_id>/feedback/', coach_views.CoachFoodLogFeedbackView.as_view(), name='coach-food-feedback'),
    path('coach/feedback/<int:feedback_id>/', coach_views.CoachFeedbackDetailView.as_view(), name='coach-feedback'),
    path('coach/instructions/<int:pk>/', coach_views.CoachInstructionDetailView.as_view(), name='coach-instruction'),
    path('coach/instructions/<int:pk>/comments/', coach_views.CoachInstructionCommentView.as_view(), name='coach-instruction-comments'),
    path('coach/instructions/<int:pk>/progress/', coach_views.CoachWorkoutProgressView.as_view(), name='coach-workout-progress'),

    path('coach/community/posts/', moderation.ModerationQueueView.as_view(), name='coach-community-posts'),
    path('coach/community/posts/<int:pk>/moderate/', moderation.ModeratePostView.as_view(), name='coach-community-moderate'),
    path('coach/community/comments/<int:pk>/hide/', moderation.ModerateCommentView.as_view(), name='coach-community-comment-hide'),

    # Web console pages
    path('web/settings/', views_web.member_app_settings, name='member-app-settings'),
    path('web/settings/bulk-enable/', views_web.member_app_bulk_enable, name='member-app-bulk-enable'),
    path('web/community/', views_web.community_moderation, name='community-moderation'),
    path('web/members/<int:pk>/coaching/', views_web.member_coaching, name='member-coaching'),
    path('web/members/<int:pk>/coaching/meals/<int:log_id>/feedback/', views_web.coaching_feedback, name='member-coaching-feedback'),
    path('web/members/<int:pk>/coaching/instructions/new/', views_web.coaching_instruction_form, name='member-coaching-instruction-new'),
    path('web/members/<int:pk>/coaching/instructions/<int:instruction_id>/', views_web.coaching_instruction_form, name='member-coaching-instruction-edit'),
    path('web/members/<int:pk>/coaching/instructions/<int:instruction_id>/comment/', views_web.coaching_comment, name='member-coaching-comment'),
    path('web/members/<int:pk>/coaching/instructions/<int:instruction_id>/action/', views_web.coaching_instruction_action, name='member-coaching-instruction-action'),
]
