from django.urls import path
from . import api, views_user

urlpatterns = [
    # Server-side Views (Dashboard/Web)
    path('list/', views_user.payment_list, name='payment-list'),
    path('create/', views_user.payment_create, name='payment-create'),
    path('detail/<int:pk>/', views_user.payment_detail, name='payment-detail'),
    path('invoice/<int:pk>/', views_user.payment_invoice, name='payment-invoice'),

    # REST API endpoints (For mobile app & integrations - Separated in api.py)
    path('api/list/', api.PaymentViewSet.as_view({'get': 'list', 'post': 'create'}), name='api-payment-list'),
    path('api/stats/', api.PaymentViewSet.as_view({'get': 'stats'}), name='api-payment-stats'),
    path('api/<int:pk>/', api.PaymentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='api-payment-detail'),
]