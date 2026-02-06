from django.urls import path
from . import views_user

urlpatterns = [
    # Member Management
    path('user/members/', views_user.member_list, name='member-list'),
    path('user/members/add/', views_user.member_create, name='member-create'),
    path('user/members/<int:pk>/', views_user.member_detail, name='member-detail'),
    path('user/members/<int:pk>/edit/', views_user.member_edit, name='member-edit'),
    path('user/members/<int:pk>/delete/', views_user.member_delete, name='member-delete'),
    path('user/members/<int:pk>/subscription/add/', views_user.member_add_subscription, name='member-subscription-add'),
    path('user/members/installment/<int:pk>/pay/', views_user.installment_pay, name='installment-pay'),
]