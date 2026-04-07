from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import FinanceTransaction
from .serializers import FinanceTransactionSerializer
from django.db.models import Sum
from django.utils import timezone
import calendar
from datetime import datetime

def get_date_range(request):
    """Helper to extract start_date and end_date from requests"""
    today = timezone.now().date()
    default_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    default_end = today.replace(day=last_day)
    
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else default_end
    except ValueError:
        start_date = default_start
        end_date = default_end
        
    return start_date, end_date

class FinanceTransactionViewSet(viewsets.ModelViewSet):
    """
    API for managing Finance Transactions (Income and Expenses).
    Gym Admins can view/create both.
    Staff and Branch Managers can only view/create Expenses.
    Contains optional date filtering via ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    serializer_class = FinanceTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        start_date, end_date = get_date_range(self.request)

        # Base filter applied with date range
        base_qs = FinanceTransaction.objects.filter(is_deleted=False, date__gte=start_date, date__lte=end_date)
        
        # Super admin
        if user.role == 'admin':
            return base_qs
            
        # Gym Admin has full access to their gym's finances
        if user.role == 'gym_admin' and user.gym:
            return base_qs.filter(gym=user.gym)
            
        # Staff and Branch Managers can only view EXPENSES for their branch
        if user.role in ['staff', 'branch_admin', 'trainer'] and user.branch:
            return base_qs.filter(
                branch=user.branch, 
                transaction_type='Expense'
            )
            
        return FinanceTransaction.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        gym = user.gym
        branch = user.branch

        # Gym Admin can create Income or Expense, but normally income is auto-generated.
        # We allow them to create any.
        if user.role == 'gym_admin':
            # They might omit branch if it's a global gym expense, use what they pass, or their mapped branch
            serializer.save(gym=gym, recorded_by=user)
        else:
            # Staff and Branch Managers are FORCED to only create Expenses mapped to their branch
            serializer.save(
                gym=gym, 
                branch=branch, 
                transaction_type='Expense',
                recorded_by=user
            )

class FinanceStatsAPIView(APIView):
    """
    Provides Finance stats (Income, Expense, Balance).
    Restricted to Gym Admins.
    Contains optional date filtering via ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Only Gym Admins can view global finance stats
        if user.role != 'gym_admin':
            return Response(
                {"error": "Access denied. Only Gym Administrators can view finance stats."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if not user.gym:
             return Response(
                {"error": "No gym associated."},
                status=status.HTTP_400_BAD_REQUEST
            )
             
        start_date, end_date = get_date_range(request)
        
        # Optional: filter by branch if branch_id is passed
        branch_id = request.query_params.get('branch_id')
        
        queryset = FinanceTransaction.objects.filter(
            gym=user.gym, 
            is_deleted=False,
            date__gte=start_date, 
            date__lte=end_date
        )
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        total_income = queryset.filter(transaction_type='Income').aggregate(sum=Sum('amount'))['sum'] or 0
        total_expense = queryset.filter(transaction_type='Expense').aggregate(sum=Sum('amount'))['sum'] or 0
        balance = total_income - total_expense
        
        return Response({
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance,
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d')
        })
