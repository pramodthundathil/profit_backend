from rest_framework import serializers
from .models import Payment, DiscountCoupon
from members.models import Member, Subscription, SubscriptionInstallment

class MemberShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'member_id', 'first_name', 'last_name', 'full_name', 'mobile_number']

class SubscriptionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['id', 'subscription_type', 'start_date', 'end_date', 'final_amount', 'amount_paid', 'balance_amount']

class PaymentSerializer(serializers.ModelSerializer):
    member_details = MemberShortSerializer(source='member', read_only=True)
    subscription_details = SubscriptionShortSerializer(source='subscription', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'subscription', 'member', 'installment', 
            'amount', 'payment_method', 'is_installment', 
            'installment_number', 'payment_date', 'created_at', 
            'status', 'transaction_id', 'receipt_number', 
            'notes', 'collected_by', 'offer', 'discount_amount',
            'member_details', 'subscription_details'
        ]
        read_only_fields = ['receipt_number', 'created_at']

class PaymentSummarySerializer(serializers.Serializer):
    total_collected_mtd = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_collected_prev_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending_due_mtd = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_mtd = serializers.DecimalField(max_digits=15, decimal_places=2)
    discounts_mtd = serializers.DecimalField(max_digits=15, decimal_places=2)
