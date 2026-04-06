from rest_framework import serializers
from .models import Member, Subscription
from utils.models import TypeSubscription

class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for member subscriptions"""
    subscription_type_name = serializers.CharField(source='subscription_type.name', read_only=True)
    duration_display = serializers.CharField(read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'subscription_type', 'subscription_type_name', 
            'duration', 'duration_unit', 'duration_display',
            'start_date', 'end_date', 'status', 
            'final_amount', 'amount_paid', 'balance_amount',
            'days_remaining', 'is_fully_paid'
        ]

class MemberMobileListSerializer(serializers.ModelSerializer):
    """Optimized serializer for mobile member listing"""
    full_name = serializers.CharField(read_only=True)
    active_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'full_name', 'mobile_number', 
            'photo', 'membership_status', 'is_active',
            'active_subscription'
        ]

    def get_active_subscription(self, obj):
        """Return basic info about current active subscription if any"""
        sub = obj.current_subscription
        if sub:
            return {
                'id': sub.id,
                'end_date': sub.end_date,
                'days_remaining': sub.days_remaining,
                'plan_name': sub.subscription_type.name if sub.subscription_type else "Custom"
            }
        return None

class MemberDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for a member including all subscriptions"""
    full_name = serializers.CharField(read_only=True)
    subscriptions = SubscriptionSerializer(many=True, read_only=True)
    age = serializers.IntegerField(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'first_name', 'last_name', 'full_name',
            'mobile_number', 'email', 'date_of_birth', 'age', 'gender',
            'address', 'photo', 'id_proof', 'membership_status',
            'is_active', 'height', 'weight', 'bmi', 'blood_group',
            'medical_history', 'emergency_contact_name', 'emergency_contact_number',
            'registration_date', 'subscriptions'
        ]

class MemberStatsSerializer(serializers.Serializer):
    """Serializer for member dashboard statistics"""
    total_members = serializers.IntegerField()
    active_members = serializers.IntegerField()
    expiring_members = serializers.IntegerField()
    expired_members = serializers.IntegerField()
