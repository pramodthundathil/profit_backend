from django.shortcuts import get_object_or_404
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
                # For branch managers, force the branch from their profile
                branch = None
                if user.role == 'branch_admin' and user.branch:
                    branch = user.branch
                
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
    serializer = MemberDetailSerializer(member, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
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
        subscription = serializer.save(member=member)
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
