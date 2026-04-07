from rest_framework import serializers
from .models import FinanceTransaction
from home.serializers import CustomUserSerializer, GymBranchSerializer

class FinanceTransactionSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    
    class Meta:
        model = FinanceTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'date', 'description', 
            'category', 'receipt_number', 'branch', 'branch_name', 
            'payment', 'recorded_by', 'recorded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'recorded_by']
