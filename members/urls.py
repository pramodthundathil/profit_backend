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
    path('user/members/installment/<int:pk>/pay/', views_user.installment_pay, name='installment-pay'),
    path('user/subscriptions/', views_user.subscription_list, name='subscription-list'),
    path('user/subscriptions/<int:pk>/', views_user.subscription_detail, name='subscription-detail'),

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