from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Batch_DB, TypeSubscription, SubscriptionPeriod
from .serializers import BatchSerializer, TypeSubscriptionSerializer, SubscriptionPeriodSerializer
from home.permissions import IsSuperAdmin
from drf_yasg.utils import swagger_auto_schema

class GymConfigPermission(permissions.BasePermission):
    """
    Custom permission for Gym Configuration:
    - List/Create: Gym Admin, Branch Admin, Staff, Trainer
    - Update/Delete: Gym Admin only
    - All actions restricted to user's gym
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.gym:
            return False
            
        # Allowed roles for read/create
        allowed_roles = ['gym_admin', 'branch_admin', 'staff', 'trainer']
        if request.user.role in allowed_roles:
            # If creating or reading, allow
            if request.method in ['GET', 'POST', 'HEAD', 'OPTIONS']:
                return True
            # If update/delete, only gym_admin
            if request.user.role == 'gym_admin':
                 return True
                 
        return False

    def has_object_permission(self, request, view, obj):
        # Strict isolation: object gym must match user gym
        return obj.gym == request.user.gym

class BatchViewSet(viewsets.ModelViewSet):
    serializer_class = BatchSerializer
    permission_classes = [GymConfigPermission]

    @swagger_auto_schema(tags=['User/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return Batch_DB.objects.filter(gym=self.request.user.gym)

    def perform_create(self, serializer):
        serializer.save(gym=self.request.user.gym)

class TypeSubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = TypeSubscriptionSerializer
    permission_classes = [GymConfigPermission]

    @swagger_auto_schema(tags=['User/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return TypeSubscription.objects.filter(gym=self.request.user.gym)

    def perform_create(self, serializer):
        serializer.save(gym=self.request.user.gym)

class SubscriptionPeriodViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionPeriodSerializer
    permission_classes = [GymConfigPermission]

    @swagger_auto_schema(tags=['User/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['User/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        return SubscriptionPeriod.objects.filter(gym=self.request.user.gym)

    def perform_create(self, serializer):
        serializer.save(gym=self.request.user.gym)


# --- Super Admin ViewSets ---

class AdminBatchViewSet(viewsets.ModelViewSet):
    queryset = Batch_DB.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ['gym']

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

class AdminTypeSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = TypeSubscription.objects.all()
    serializer_class = TypeSubscriptionSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ['gym']

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

class AdminSubscriptionPeriodViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPeriod.objects.all()
    serializer_class = SubscriptionPeriodSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ['gym']

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Admin/Configuration'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
