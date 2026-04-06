from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Member, Subscription
from .serializers import (
    MemberMobileListSerializer,
    MemberDetailSerializer,
    SubscriptionSerializer,
)

# ============================================================================
# MEMBER API VIEWS
# ============================================================================

@swagger_auto_schema(
    method='get',
    operation_description="Get optimized member list for mobile app with dashboard statistics",
    responses={200: MemberMobileListSerializer(many=True)},
    manual_parameters=[
        openapi.Parameter('branch', openapi.IN_QUERY, description="Filter by branch ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter('search', openapi.IN_QUERY, description="Search by name/phone/ID", type=openapi.TYPE_STRING),
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mobile_member_list(request):
    """Optimized member list for mobile with dashboard stats"""
    user = request.user
    if not user.gym:
        return Response({"error": "No gym associated"}, status=status.HTTP_400_BAD_REQUEST)

    branch_filter = request.GET.get('branch', '')
    search_query = request.GET.get('search', '')
    
    members = Member.objects.filter(gym=user.gym, is_active=True).select_related('branch')

    # Apply permissions
    if user.role == 'branch_admin' and user.branch:
        members = members.filter(branch=user.branch)
    elif branch_filter:
        members = members.filter(branch_id=branch_filter)
        
    # Apply search
    if search_query:
        members = members.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(mobile_number__icontains=search_query) |
            Q(member_id__icontains=search_query)
        )

    # Calculate stats for the user's scope
    today = timezone.now().date()
    expiring_soon = today + timedelta(days=7)
    
    active_count = members.filter(membership_status='Active').count()
    expiring_count = members.filter(
        subscriptions__status='Active',
        subscriptions__end_date__gte=today,
        subscriptions__end_date__lte=expiring_soon
    ).distinct().count()
    expired_count = members.filter(membership_status='Expired').count()

    # Serialization
    member_data = MemberMobileListSerializer(members[:100], many=True).data 
    
    return Response({
        "stats": {
            "total": members.count(),
            "active": active_count,
            "expiring": expiring_count,
            "expired": expired_count
        },
        "members": member_data
    })

@swagger_auto_schema(
    method='post',
    operation_description="Create a new member (photo and id_proof are optional)",
    request_body=MemberDetailSerializer,
    responses={201: MemberDetailSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def member_create_api(request):
    """API view to create a member"""
    user = request.user
    if not user.gym:
        return Response({"error": "No gym associated"}, status=status.HTTP_400_BAD_REQUEST)

    serializer = MemberDetailSerializer(data=request.data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                # Default branch logic
                branch_id = request.data.get('branch')
                branch = None
                
                if user.role == 'branch_admin' and user.branch:
                    branch = user.branch
                elif branch_id:
                    # Verify branch belongs to same gym
                    from home.models import GymBranch
                    branch = get_object_or_404(GymBranch, id=branch_id, gym=user.gym)
                
                # Save member
                serializer.save(gym=user.gym, branch=branch)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@swagger_auto_schema(
    method='get',
    operation_description="Get member details by ID",
    responses={200: MemberDetailSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_detail_api(request, pk):
    """API view to get member details"""
    member = get_object_or_404(Member, pk=pk, gym=request.user.gym)
    serializer = MemberDetailSerializer(member)
    return Response(serializer.data)

@swagger_auto_schema(
    method='put',
    operation_description="Update member details",
    request_body=MemberDetailSerializer,
    responses={200: MemberDetailSerializer}
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def member_update_api(request, pk):
    """API view to update a member"""
    member = get_object_or_404(Member, pk=pk, gym=request.user.gym)
    
    # Permission check: branch admin can only update their own members
    if request.user.role == 'branch_admin' and member.branch != request.user.branch:
        return Response({"error": "Unauthorized to update members from other branches"}, 
                        status=status.HTTP_403_FORBIDDEN)

    serializer = MemberDetailSerializer(member, data=request.data, partial=True)
    if serializer.is_valid():
        # Handle branch update if provided and user is gym_admin or admin
        if request.user.role in ['gym_admin', 'admin'] and 'branch' in request.data:
            branch_id = request.data.get('branch')
            if branch_id:
                from home.models import GymBranch
                branch = get_object_or_404(GymBranch, id=branch_id, gym=request.user.gym)
                serializer.save(branch=branch)
            else:
                serializer.save(branch=None)
        else:
            serializer.save()
            
        member.update_membership_status()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='delete',
    operation_description="Deactivate a member",
    responses={204: "No Content"}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def member_delete_api(request, pk):
    """API view to deactivate a member"""
    member = get_object_or_404(Member, pk=pk, gym=request.user.gym)
    member.is_active = False
    member.membership_status = 'Cancelled'
    member.save()
    return Response(status=status.HTTP_204_NO_CONTENT)

# ============================================================================
# SUBSCRIPTION API VIEWS
# ============================================================================

@swagger_auto_schema(
    method='post',
    operation_description="Add a subscription to a member",
    request_body=SubscriptionSerializer,
    responses={201: SubscriptionSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscription_create_api(request, member_id):
    """API view to add a subscription"""
    member = get_object_or_404(Member, pk=member_id, gym=request.user.gym)
    serializer = SubscriptionSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            subscription = serializer.save(member=member)
            
            # If amount_paid is provided, create a Payment record
            amount_paid = request.data.get('amount_paid', 0)
            if float(amount_paid) > 0:
                from payments.models import Payment
                Payment.objects.create(
                    subscription=subscription,
                    member=member,
                    amount=amount_paid,
                    payment_method=request.data.get('payment_method', 'Cash'),
                    status='Completed',
                    notes="Initial payment during subscription creation"
                )
            
            member.update_membership_status()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='put',
    operation_description="Update a subscription",
    request_body=SubscriptionSerializer,
    responses={200: SubscriptionSerializer}
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def subscription_update_api(request, pk):
    """API view to update a subscription"""
    subscription = get_object_or_404(Subscription, pk=pk, member__gym=request.user.gym)
    serializer = SubscriptionSerializer(subscription, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        subscription.member.update_membership_status()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='delete',
    operation_description="Cancel a subscription",
    responses={204: "No Content"}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def subscription_delete_api(request, pk):
    """API view to cancel/delete a subscription"""
    subscription = get_object_or_404(Subscription, pk=pk, member__gym=request.user.gym)
    subscription.status = 'Cancelled'
    subscription.save()
    subscription.member.update_membership_status()
    return Response(status=status.HTTP_204_NO_CONTENT)

@swagger_auto_schema(
    method='post',
    operation_description="Process payment for an installment (Full or Partial)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'payment_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['Full', 'Partial'], default='Full'),
            'amount': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL, description="Amount to pay. Defaults to installment balance."),
            'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['Cash', 'UPI', 'Card', 'Bank Transfer'], default='Cash'),
            'expiry_date': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE, description="Custom sub expiry date. Recommended for Partial payments."),
        }
    ),
    responses={200: "Success message", 400: "Error message"}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def installment_pay_api(request, pk):
    """API view to mark an installment as Paid"""
    from .models import SubscriptionInstallment
    from django.utils import timezone
    
    installment = get_object_or_404(SubscriptionInstallment, pk=pk, subscription__member__gym=request.user.gym)
    
    if installment.status == 'Paid':
        return Response({"error": "Installment is already paid"}, status=status.HTTP_400_BAD_REQUEST)
        
    payment_type = request.data.get('payment_type', 'Full')
    amount = Decimal(str(request.data.get('amount', installment.remaining_amount)))
    payment_method = request.data.get('payment_method', 'Cash')
    expiry_date = request.data.get('expiry_date')

    with transaction.atomic():
        # 1. Update Installment
        installment.amount_paid += amount
        if installment.amount_paid >= installment.amount:
            installment.status = 'Paid'
        else:
            installment.status = 'Partially Paid'
        
        installment.paid_date = timezone.now().date()
        installment.save()
        
        # 2. Create Payment record
        from payments.models import Payment
        sub = installment.subscription
        Payment.objects.create(
            subscription=sub,
            member=sub.member,
            installment=installment,
            amount=amount,
            payment_method=payment_method,
            is_installment=True,
            installment_number=installment.installment_number,
            status='Completed',
            notes=f"API: {payment_type} payment for installment {installment.installment_number}"
        )
        # Note: update_payment_status is called automatically by Payment.save()
        
        # 3. Explicitly set expiry date if it's a partial payment and user provided a date
        if payment_type == 'Partial' and expiry_date:
            sub.end_date = expiry_date
            sub.save(update_fields=['end_date'])
        
        return Response({
            "message": f"Payment of {amount} for installment {installment.installment_number} recorded successfully.",
            "status": installment.status,
            "remaining_amount": float(installment.remaining_amount)
        })
