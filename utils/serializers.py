from rest_framework import serializers
from .models import Batch_DB, TypeSubscription, SubscriptionPeriod

class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch_DB
        fields = ['id', 'batch_name', 'batch_status', 'batch_time']
        read_only_fields = ['id']

class TypeSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeSubscription
        fields = ['id', 'name', 'is_active']
        read_only_fields = ['id']

class SubscriptionPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPeriod
        fields = ['id', 'period']
        read_only_fields = ['id']
