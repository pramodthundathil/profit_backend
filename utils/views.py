from django.db import IntegrityError, transaction
from rest_framework import serializers, viewsets, permissions, status
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

class GymUniqueMixin:
    """Saves under the user's gym and reports duplicates as a 400 instead of a 500."""
    duplicate_message = 'This already exists.'

    def _save(self, serializer, **kwargs):
        try:
            with transaction.atomic():
                serializer.save(**kwargs)
        except IntegrityError:
            raise serializers.ValidationError({'detail': self.duplicate_message})

    def perform_create(self, serializer):
        self._save(serializer, gym=self.request.user.gym)

    def perform_update(self, serializer):
        self._save(serializer)


class BatchViewSet(GymUniqueMixin, viewsets.ModelViewSet):
    duplicate_message = 'A batch with this name and time already exists.'
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
        if getattr(self, 'swagger_fake_view', False):
            return Batch_DB.objects.none()
        return Batch_DB.objects.filter(gym=self.request.user.gym)

class TypeSubscriptionViewSet(GymUniqueMixin, viewsets.ModelViewSet):
    duplicate_message = 'A subscription type with this name already exists.'
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
        if getattr(self, 'swagger_fake_view', False):
            return TypeSubscription.objects.none()
        return TypeSubscription.objects.filter(gym=self.request.user.gym)

class SubscriptionPeriodViewSet(GymUniqueMixin, viewsets.ModelViewSet):
    duplicate_message = 'This subscription period already exists.'
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
        if getattr(self, 'swagger_fake_view', False):
            return SubscriptionPeriod.objects.none()
        return SubscriptionPeriod.objects.filter(gym=self.request.user.gym)


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
