from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import (
    CustomUser, GymOffice, GymBranch, LicenseKey,
    SubscriptionHistory, PaymentTransaction, HikConfigurationDb
)
from .serializers import (
    CustomUserSerializer, UserCreateSerializer, UserUpdateSerializer,
    ChangePasswordSerializer, GymOfficeSerializer, GymOfficeCreateSerializer,
    GymBranchSerializer, LicenseKeySerializer, SubscriptionHistorySerializer,
    PaymentTransactionSerializer, GymRegistrationSerializer, HikConfigurationDbSerializer,
    CustomTokenObtainPairSerializer
)
from .permissions import (
    IsSuperAdmin, IsGymAdmin, IsBranchAdmin, CanManageGym,
    CanManageBranch, CanCreateBranch, CanManageUsers, IsOwnerOrReadOnly,
    HasActiveSubscription, CanViewBranch, CanManageHikConfiguration
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

class LoginRequestSerializer(serializers.Serializer):
    """Clean serializer for Swagger Login documentation"""
    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(
        style={'input_type': 'password'},
        help_text="User's password"
    )

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom Login view for Swagger documentation
    """
    @swagger_auto_schema(
        tags=['Auth/Public'],
        operation_description="Login with email and password to receive JWT tokens.",
        request_body=LoginRequestSerializer,
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'access': openapi.Schema(type=openapi.TYPE_STRING),
                        'refresh': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            status.HTTP_401_UNAUTHORIZED: "Invalid credentials"
        }
    )
    def post(self, request, *args, **kwargs):
        # Use our custom serializer
        serializer = CustomTokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"detail": "No active account found with the given credentials"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )


class GymRegistrationView(APIView):
    """
    Public endpoint for gym registration
    """
    permission_classes = [permissions.AllowAny]
    @swagger_auto_schema(
        operation_description="Public endpoint to register a new gym and its primary administrator account.",
        request_body=GymRegistrationSerializer,
        tags=['Auth/Public'],
        responses={
            status.HTTP_201_CREATED: openapi.Response(
                description="Gym registered successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'gym': openapi.Schema(type=openapi.TYPE_OBJECT),
                        'admin': openapi.Schema(type=openapi.TYPE_OBJECT)
                    }
                )
            ),
            status.HTTP_400_BAD_REQUEST: openapi.Response(
                description="Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'errors': openapi.Schema(type=openapi.TYPE_OBJECT)
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = GymRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            
            return Response({
                'message': 'Gym registered successfully',
                'gym': GymOfficeSerializer(result['gym']).data,
                'admin': CustomUserSerializer(result['admin']).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GymOfficeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Gym Office management
    Only super admin can create/delete gyms
    """
    queryset = GymOffice.objects.all()
    serializer_class = GymOfficeSerializer # Base serializer for Swagger
    
    def get_serializer_class(self):
        if self.action == 'create':
            return GymOfficeCreateSerializer
        return GymOfficeSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsSuperAdmin()]
        elif self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), CanManageGym()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return GymOffice.objects.none()
        user = self.request.user
        
        # Super admin sees all gyms
        if user.role == 'admin':
            return GymOffice.objects.all()
        
        # Gym admin sees only their gym
        if user.role == 'gym_admin' and user.gym:
            return GymOffice.objects.filter(id=user.gym.id)
        
        return GymOffice.objects.none()
    
    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'], request_body=GymOfficeCreateSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    @action(detail=True, methods=['get'])
    def subscription_status(self, request, pk=None):
        """Get detailed subscription status"""
        gym = self.get_object()
        status_data = gym.get_subscription_status()
        return Response(status_data)
    
    @swagger_auto_schema(
        tags=['Admin/Gym Management'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'months': openapi.Schema(type=openapi.TYPE_INTEGER, default=12)
            }
        )
    )
    @action(detail=True, methods=['post'])
    def extend_subscription(self, request, pk=None):
        """Extend subscription (admin only)"""
        gym = self.get_object()
        months = request.data.get('months', 12)
        
        try:
            months = int(months)
            if months <= 0 or months > 24:
                return Response(
                    {'error': 'Months must be between 1 and 24'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid months value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_end_date = gym.extend_subscription(months=months)
        
        return Response({
            'message': f'Subscription extended by {months} months',
            'new_expiry_date': new_end_date,
            'subscription_status': gym.get_subscription_status()
        })
    
    @swagger_auto_schema(tags=['Admin/Gym Management'])
    @action(detail=True, methods=['get'])
    def branches(self, request, pk=None):
        """Get all branches of this gym"""
        gym = self.get_object()
        branches = gym.gym_branches.all()
        serializer = GymBranchSerializer(branches, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(tags=['Admin/Gym Management'])
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users of this gym"""
        gym = self.get_object()
        users = gym.users.all()
        serializer = CustomUserSerializer(users, many=True)
        return Response(serializer.data)


class GymBranchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Gym Branch management
    """
    queryset = GymBranch.objects.all()
    serializer_class = GymBranchSerializer
    
    @swagger_auto_schema(tags=['Admin/Branch Management'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Branch Management'], request_body=GymBranchSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Branch Management'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Branch Management'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Branch Management'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Branch Management'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), CanCreateBranch(), HasActiveSubscription()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanManageBranch()]
        return [permissions.IsAuthenticated(), CanViewBranch()]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return GymBranch.objects.none()
        user = self.request.user
        
        # Super admin sees all branches
        if user.role == 'admin':
            return GymBranch.objects.all()
        
        # Gym admin sees all branches in their gym
        if user.role == 'gym_admin' and user.gym:
            return GymBranch.objects.filter(gym=user.gym)
        
        # Branch admin and staff see only their branch
        if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
            return GymBranch.objects.filter(id=user.branch.id)
        
        return GymBranch.objects.none()
    
    def perform_create(self, serializer):
        """Set gym automatically for gym admin"""
        user = self.request.user
        
        if user.role == 'gym_admin':
            serializer.save(gym=user.gym, created_by=user)
        elif user.role == 'admin':
            serializer.save(created_by=user)
        else:
            return Response({'error': 'You are not authorized to create a branch'}, status=status.HTTP_403_FORBIDDEN)
    
    @swagger_auto_schema(tags=['Admin/Branch Management'])
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in this branch"""
        branch = self.get_object()
        users = branch.users.all()
        serializer = CustomUserSerializer(users, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(tags=['Admin/Branch Management'])
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle branch active status"""
        branch = self.get_object()
        branch.is_active = not branch.is_active
        branch.save()
        
        return Response({
            'message': f"Branch {'activated' if branch.is_active else 'deactivated'} successfully",
            'is_active': branch.is_active
        })


class CustomUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer # Base serializer for Swagger
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return CustomUserSerializer
    
    @swagger_auto_schema(tags=['User Management'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User Management'], request_body=UserCreateSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User Management'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User Management'], request_body=UserUpdateSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User Management'], request_body=UserUpdateSerializer)
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User Management'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanManageUsers(), HasActiveSubscription()]
        elif self.action == 'me':
            return [permissions.IsAuthenticated()]
        elif self.action == 'change_password':
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CustomUser.objects.none()
        user = self.request.user
        
        # Super admin sees all users
        if user.role == 'admin':
            return CustomUser.objects.all()
        
        # Gym admin sees all users in their gym
        if user.role == 'gym_admin' and user.gym:
            return CustomUser.objects.filter(gym=user.gym)
        
        # Branch admin sees users in their branch
        if user.role == 'branch_admin' and user.branch:
            return CustomUser.objects.filter(branch=user.branch)
        
        # Others see only themselves
        return CustomUser.objects.filter(id=user.id)
    
    def perform_create(self, serializer):
        """Auto-assign gym/branch for non-admin users"""
        user = self.request.user
        
        if user.role == 'gym_admin':
            # Gym admin creates users for their gym
            serializer.save(gym=user.gym)
        elif user.role == 'branch_admin':
            # Branch admin creates users for their branch
            serializer.save(gym=user.gym, branch=user.branch)
        else:
            serializer.save()
    
    @swagger_auto_schema(tags=['User Management'])
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user details"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @swagger_auto_schema(tags=['User Management'], request_body=ChangePasswordSerializer)
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change user password"""
        user = self.get_object()
        
        # Users can only change their own password unless admin
        if request.user != user and request.user.role not in ['admin', 'gym_admin']:
            return Response(
                {'error': 'You can only change your own password'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(tags=['User Management'])
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle user active status"""
        user = self.get_object()
        
        # Cannot deactivate super admin
        if user.role == 'admin':
            return Response(
                {'error': 'Cannot deactivate super admin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cannot deactivate yourself
        if user == request.user:
            return Response(
                {'error': 'Cannot deactivate yourself'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_active = not user.is_active
        user.save()
        
        return Response({
            'message': f"User {'activated' if user.is_active else 'deactivated'} successfully",
            'is_active': user.is_active
        })
    
    @swagger_auto_schema(
        tags=['User Management'],
        manual_parameters=[
            openapi.Parameter('role', openapi.IN_QUERY, description="Role to filter by", type=openapi.TYPE_STRING)
        ]
    )
    @action(detail=False, methods=['get'])
    def by_role(self, request):
        """Filter users by role"""
        role = request.query_params.get('role')
        
        if not role:
            return Response(
                {'error': 'Role parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(role=role)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        tags=['User Management'],
        manual_parameters=[
            openapi.Parameter('branch_id', openapi.IN_QUERY, description="Branch ID to filter by", type=openapi.TYPE_INTEGER)
        ]
    )
    @action(detail=False, methods=['get'])
    def by_branch(self, request):
        """Filter users by branch"""
        branch_id = request.query_params.get('branch_id')
        
        if not branch_id:
            return Response(
                {'error': 'Branch ID parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(branch_id=branch_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class LicenseKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for License Key management (Super Admin only)
    """
    queryset = LicenseKey.objects.all()
    serializer_class = LicenseKeySerializer
    permission_classes = [IsSuperAdmin]
    
    @swagger_auto_schema(tags=['Admin/Licensing'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Licensing'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Licensing'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Licensing'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Licensing'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Licensing'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Admin/Licensing'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'gym_id': openapi.Schema(type=openapi.TYPE_INTEGER)
            },
            required=['gym_id']
        )
    )
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign license key to a gym"""
        license_key = self.get_object()
        gym_id = request.data.get('gym_id')
        
        if not gym_id:
            return Response(
                {'error': 'Gym ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            gym = GymOffice.objects.get(id=gym_id)
        except GymOffice.DoesNotExist:
            return Response(
                {'error': 'Gym not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if license_key.is_used:
            return Response(
                {'error': 'License key is already used'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        license_key.is_used = True
        license_key.assigned_to = gym
        license_key.save()
        
        gym.license_key = license_key
        gym.save()
        
        return Response({
            'message': 'License key assigned successfully',
            'license': LicenseKeySerializer(license_key).data
        })
    
    @swagger_auto_schema(tags=['Admin/Licensing'])
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get all available (unused) license keys"""
        licenses = LicenseKey.objects.filter(is_used=False)
        serializer = self.get_serializer(licenses, many=True)
        return Response(serializer.data)


class SubscriptionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing subscription history
    """
    queryset = SubscriptionHistory.objects.all()
    serializer_class = SubscriptionHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Gym Management'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SubscriptionHistory.objects.none()
        user = self.request.user
        
        # Super admin sees all
        if user.role == 'admin':
            return SubscriptionHistory.objects.all()
        
        # Gym admin sees their gym's history
        if user.role == 'gym_admin' and user.gym:
            return SubscriptionHistory.objects.filter(gym=user.gym)
        
        return SubscriptionHistory.objects.none()


class PaymentTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for payment transactions
    """
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsGymAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return PaymentTransaction.objects.none()
        user = self.request.user
        
        # Super admin sees all
        if user.role == 'admin':
            return PaymentTransaction.objects.all()
        
        # Gym admin sees their gym's transactions
        if user.role == 'gym_admin' and user.gym:
            return PaymentTransaction.objects.filter(gym=user.gym)
        
        return PaymentTransaction.objects.none()
    
    @swagger_auto_schema(
        tags=['Admin/Payments'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'razorpay_payment_id': openapi.Schema(type=openapi.TYPE_STRING),
                'razorpay_signature': openapi.Schema(type=openapi.TYPE_STRING)
            },
            required=['razorpay_payment_id', 'razorpay_signature']
        )
    )
    @action(detail=True, methods=['post'])
    def verify_payment(self, request, pk=None):
        """Verify Razorpay payment"""
        transaction = self.get_object()
        
        # Add your Razorpay verification logic here
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        
        if not razorpay_payment_id or not razorpay_signature:
            return Response(
                {'error': 'Payment ID and signature are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update transaction
        transaction.razorpay_payment_id = razorpay_payment_id
        transaction.razorpay_signature = razorpay_signature
        transaction.status = 'completed'
        transaction.save()
        
        # Extend subscription
        months = 12  # Default 1 year, adjust based on plan
        transaction.gym.extend_subscription(months=months, payment_transaction=transaction)
        
        return Response({
            'message': 'Payment verified and subscription extended',
            'transaction': PaymentTransactionSerializer(transaction).data
        })


class DashboardStatsView(APIView):
    """
    Get dashboard statistics based on user role
    """
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]
    
    @swagger_auto_schema(tags=['Stats/Dashboard'])
    def get(self, request):
        user = request.user
        stats = {}
        
        if user.role == 'admin':
            # Super admin dashboard
            stats = {
                'total_gyms': GymOffice.objects.count(),
                'active_gyms': GymOffice.objects.filter(is_active=True).count(),
                'total_branches': GymBranch.objects.count(),
                'total_users': CustomUser.objects.count(),
                'active_licenses': LicenseKey.objects.filter(is_used=True).count(),
                'available_licenses': LicenseKey.objects.filter(is_used=False).count(),
            }
        
        elif user.role == 'gym_admin' and user.gym:
            # Gym admin dashboard
            gym = user.gym
            stats = {
                'gym_name': gym.name,
                'subscription_status': gym.get_subscription_status(),
                'total_branches': gym.gym_branches.filter(is_active=True).count(),
                'total_users': gym.users.filter(is_active=True).count(),
                'total_staff': gym.users.filter(role='staff', is_active=True).count(),
                'total_trainers': gym.users.filter(role='trainer', is_active=True).count(),
                'can_create_branch': gym.can_create_branch(),
            }
        
        elif user.role == 'branch_admin' and user.branch:
            # Branch admin dashboard
            branch = user.branch
            stats = {
                'branch_name': branch.name,
                'gym_name': branch.gym.name,
                'total_staff': branch.users.filter(role='staff', is_active=True).count(),
                'total_trainers': branch.users.filter(role='trainer', is_active=True).count(),
            }
        
        return Response(stats)


class HikConfigurationDbViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Hik Configuration management
    """
    queryset = HikConfigurationDb.objects.all()
    serializer_class = HikConfigurationDbSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageHikConfiguration]
    
    @swagger_auto_schema(tags=['Admin/Settings'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Settings'], request_body=HikConfigurationDbSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Settings'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Settings'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Settings'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Settings'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    def get_queryset(self):
        user = self.request.user
        
        if not user.is_authenticated:
            return HikConfigurationDb.objects.none()

        # Super admin
        if user.role == 'admin':
            return HikConfigurationDb.objects.all()
            
        # Gym admin
        if user.role == 'gym_admin' and user.gym:
             return HikConfigurationDb.objects.filter(
                 Q(gym=user.gym) | Q(gym_branch__gym=user.gym)
             )
        
        # Branch admin
        if user.role == 'branch_admin' and user.branch:
            return HikConfigurationDb.objects.filter(gym_branch=user.branch)
            
        return HikConfigurationDb.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        
        # Enforce branch for branch manager
        if user.role == 'branch_admin':
            serializer.save(gym_branch=user.branch)
        else:
             serializer.save()




