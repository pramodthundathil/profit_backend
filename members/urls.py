from django.urls import path
from . import views, views_user

urlpatterns = [
    # Template-based views (for dashboard/web interface)
    path('user/members/', views_user.member_list, name='member-list'),
    path('user/members/add/', views_user.member_create, name='member-create'),
    path('user/members/<int:pk>/', views_user.member_detail, name='member-detail'),
    path('user/members/<int:pk>/edit/', views_user.member_edit, name='member-edit'),
    path('user/members/<int:pk>/delete/', views_user.member_delete, name='member-delete'),
    path('user/members/<int:pk>/block/', views_user.member_block_access, name='member-block-access'),
    path('user/members/<int:pk>/unblock/', views_user.member_unblock_access, name='member-unblock-access'),
    path('user/members/<int:pk>/extend/', views_user.member_extend_access, name='member-extend-access'),
    path('user/members/<int:pk>/subscription/add/', views_user.member_add_subscription, name='member-subscription-add'),
    path('user/payments/<int:pk>/receipt/', views_user.payment_receipt, name='payment-receipt'),
    path('user/members/installment/<int:pk>/pay/', views_user.installment_pay, name='installment-pay'),

    path('user/subscriptions/', views_user.subscription_list, name='subscription-list'),
    path('user/subscriptions/<int:pk>/', views_user.subscription_detail, name='subscription-detail'),
    path('user/subscriptions/<int:pk>/edit/', views_user.subscription_edit, name='subscription-edit'),
    path('user/subscriptions/<int:pk>/delete/', views_user.subscription_delete, name='subscription-delete'),


    # Health History
    path('user/members/<int:member_id>/health-history/form/', views_user.health_history_form_view, name='health-history-form'),
    path('user/members/<int:member_id>/health-history/detail/', views_user.health_history_detail_view, name='health-history-detail'),
    path('user/health-history/success/', views_user.success_on_health_history, name='health-history-success'),

    # PAR-Q Form
    path('user/members/<int:member_id>/parq/create/', views_user.parq_form_create, name='parq-create'),
    path('user/members/parq/<int:pk>/', views_user.parq_form_detail, name='parq-detail'),
    path('user/members/parq/<int:pk>/edit/', views_user.parq_form_update, name='parq-update'),

    # Public Form Links (No authentication required)
    path('public/health-history/<uuid:token>/', views_user.public_health_history_form, name='public-health-history'),
    path('public/parq/<uuid:token>/', views_user.public_parq_form, name='public-parq'),
    path('public/success/', views_user.public_success, name='public-success'),

    # REST API endpoints (for mobile app & integrations)
    path('api/mobile/list/', views.mobile_member_list, name='api-mobile-member-list'),
    
    # Member API CRUD
    path('api/members/create/', views.member_create_api, name='api-member-create'),
    path('api/members/list/', views.mobile_member_list, name='api-member-list'), # Reusing mobile list for general list
    path('api/members/<int:pk>/', views.member_detail_api, name='api-member-detail'),
    path('api/members/<int:pk>/update/', views.member_update_api, name='api-member-update'),
    path('api/members/<int:pk>/delete/', views.member_delete_api, name='api-member-delete'),
    path('api/members/<int:pk>/block/', views.member_block_access_api, name='api-member-block-access'),
    path('api/members/<int:pk>/unblock/', views.member_unblock_access_api, name='api-member-unblock-access'),
    path('api/members/<int:pk>/extend/', views.member_extend_access_api, name='api-member-extend-access'),
    
    # Subscription API CRUD
    path('api/members/<int:member_id>/subscription/create/', views.subscription_create_api, name='api-subscription-create'),
    path('api/subscription/<int:pk>/', views.subscription_detail_api, name='api-subscription-detail'),
    path('api/subscription/<int:pk>/update/', views.subscription_update_api, name='api-subscription-update'),
    path('api/subscription/<int:pk>/delete/', views.subscription_delete_api, name='api-subscription-delete'),
    path('api/installment/<int:pk>/pay/', views.installment_pay_api, name='api-installment-pay'),
    path('api/subscriptions/list/', views.subscription_list_api, name='api-subscription-list'),
]