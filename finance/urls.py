from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import FinanceTransactionViewSet, FinanceStatsAPIView
from . import views

router = DefaultRouter()
router.register(r'transactions', FinanceTransactionViewSet, basename='finance-transaction')

urlpatterns = [
    # Server-Side Web App URLs
    path('dashboard/', views.finance_dashboard, name='finance-dashboard'),
    path('add-transaction/', views.add_transaction, name='finance-add-transaction'),
    
    # Mobile App API URLs
    path('api/', include(router.urls)),
    path('api/stats/', FinanceStatsAPIView.as_view(), name='finance-api-stats'),
]