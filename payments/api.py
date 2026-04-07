from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator

from .models import Payment
from .serializers import PaymentSerializer, PaymentSummarySerializer
from members.models import Subscription, SubscriptionInstallment

from drf_yasg import openapi

@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Payments'], 
    operation_description="List payments with filtering and sorting",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Search by name, ID or receipt", type=openapi.TYPE_STRING),
        openapi.Parameter('sort', openapi.IN_QUERY, description="Sort by date (payment_date or -payment_date)", type=openapi.TYPE_STRING),
        openapi.Parameter('days', openapi.IN_QUERY, description="Number of days to look back (default 30)", type=openapi.TYPE_INTEGER),
        openapi.Parameter('branch', openapi.IN_QUERY, description="Filter by branch ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter('include_stats', openapi.IN_QUERY, description="Include summary stats in response", type=openapi.TYPE_BOOLEAN),
    ]
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Payments'], operation_description="Get specific payment details"))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Payments'], operation_description="Record a new payment"))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Payments'], operation_description="Update payment record"))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Payments'], operation_description="Partially update payment record"))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Payments'], operation_description="Delete payment record"))
class PaymentViewSet(viewsets.ModelViewSet):
    """API for managing payments"""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.gym:
             return Payment.objects.none()
        
        queryset = Payment.objects.filter(member__gym=user.gym)
        
        # Branch filtering
        branch_id = self.request.query_params.get('branch')
        if branch_id:
             queryset = queryset.filter(member__branch_id=branch_id)
        elif user.role == 'branch_admin' and user.branch:
             queryset = queryset.filter(member__branch=user.branch)
             
        # Date filtering
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        if start_date_str and end_date_str:
            try:
                queryset = queryset.filter(payment_date__gte=start_date_str, payment_date__lte=end_date_str)
            except Exception:
                pass
        else:
            # Fallback to days (Last 30 days by default)
            try:
                days = int(self.request.query_params.get('days', 30))
            except (ValueError, TypeError):
                days = 30
                
            if days > 0:
                 start_date = timezone.now().date() - timedelta(days=days)
                 queryset = queryset.filter(payment_date__gte=start_date)
        
        # Search (Member Name, ID, Receipt No)
        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(member__first_name__icontains=search_query) |
                Q(member__last_name__icontains=search_query) |
                Q(member__member_id__icontains=search_query) |
                Q(receipt_number__icontains=search_query)
            )

        # Sorting
        sort_by = self.request.query_params.get('sort', '-payment_date')
        if sort_by in ['payment_date', '-payment_date']:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-payment_date')
             
        return queryset

    def list(self, request, *args, **kwargs):
        """Include summary statistics in the list response if requested"""
        response = super().list(request, *args, **kwargs)
        if request.query_params.get('include_stats') == 'true':
            stats_data = self._calculate_stats(request.user, request)
            response.data['stats'] = stats_data
        return response

    @swagger_auto_schema(tags=['Payments'], operation_description="Get MTD (Month-to-Date) statistics for payments")
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Dedicated action for statistics"""
        if not request.user.gym:
             return Response({"error": "No gym associated"}, status=400)
        
        stats_data = self._calculate_stats(request.user, request)
        return Response(stats_data)

    def _calculate_stats(self, user, request=None):
        """Helper to calculate statistics"""
        today = timezone.now().date()
        
        start_date_str = request.query_params.get('start_date') if request else None
        end_date_str = request.query_params.get('end_date') if request else None

        if start_date_str and end_date_str:
            try:
                # Custom date range stats
                from datetime import datetime
                custom_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                custom_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                
                period_start = custom_start
                period_end = custom_end
                
                # For custom range, we just use the same range for prev_month (could improve later)
                prev_period_start = period_start - (period_end - period_start)
                prev_period_end = period_start
            except Exception:
                period_start = today.replace(day=1)
                period_end = today
                prev_period_end = period_start - timedelta(days=1)
                prev_period_start = prev_period_end.replace(day=1)
        else:
            # Default MTD
            period_start = today.replace(day=1)
            period_end = today
            prev_period_end = period_start - timedelta(days=1)
            prev_period_start = prev_period_end.replace(day=1)
        
        # Base filter for the user's gym
        base_payments = Payment.objects.filter(member__gym=user.gym, status='Completed')
        base_installments = SubscriptionInstallment.objects.filter(subscription__member__gym=user.gym)
        base_subscriptions = Subscription.objects.filter(member__gym=user.gym)
        
        if user.role == 'branch_admin' and user.branch:
             base_payments = base_payments.filter(member__branch=user.branch)
             base_installments = base_installments.filter(subscription__member__branch=user.branch)
             base_subscriptions = base_subscriptions.filter(member__branch=user.branch)

        # 1. Total Collected (Period)
        total_mtd = base_payments.filter(
            payment_date__gte=period_start, 
            payment_date__lte=period_end
        ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

        # 2. Previous Period Collection
        total_prev = base_payments.filter(
            payment_date__gte=prev_period_start, 
            payment_date__lte=prev_period_end
        ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

        # 3. Pending Due (Period)
        pending_mtd = base_installments.filter(
            due_date__gte=period_start,
            due_date__lte=period_end,
            status__in=['Pending', 'Partially Paid']
        )
        pending_due_sum = sum(inst.remaining_amount for inst in pending_mtd)

        # 4. Overdue (Period)
        overdue_mtd = base_installments.filter(
            due_date__lt=period_end,  # Use period end for overdue reference
            status__in=['Pending', 'Partially Paid', 'Overdue']
        )
        overdue_sum = sum(inst.remaining_amount for inst in overdue_mtd)

        # 5. Discounts Given (Period)
        subscriptions_mtd = base_subscriptions.filter(
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )
        discounts_sum = sum((sub.base_amount - sub.final_amount) for sub in subscriptions_mtd)

        return {
            'total_collected_mtd': total_mtd,
            'total_collected_prev_month': total_prev,
            'pending_due_mtd': pending_due_sum,
            'overdue_mtd': overdue_sum,
            'discounts_mtd': discounts_sum
        }
