from .models import Member, Subscription, SubscriptionInstallment, GymBranch
from utils.models import TypeSubscription
from rest_framework import serializers

class SubscriptionInstallmentSerializer(serializers.ModelSerializer):
    """Serializer for individual installments"""
    remaining_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = SubscriptionInstallment
        fields = ['id', 'installment_number', 'due_date', 'amount', 'amount_paid', 'remaining_amount', 'status', 'paid_date']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for member subscriptions"""
    subscription_type_name = serializers.SerializerMethodField()
    batch_name = serializers.SerializerMethodField()
    duration_display = serializers.CharField(read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    installments = SubscriptionInstallmentSerializer(many=True, read_only=True)
    
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    member_id_code = serializers.CharField(source='member.member_id', read_only=True)
    member_mobile = serializers.CharField(source='member.mobile_number', read_only=True)
    member_photo = serializers.SerializerMethodField()

    def get_subscription_type_name(self, obj):
        return obj.subscription_type.name if obj.subscription_type else "Custom"

    def get_batch_name(self, obj):
        return obj.batch.batch_name if obj.batch else "Any Time"

    def get_member_photo(self, obj):
        if obj.member and obj.member.photo:
            try:
                return obj.member.photo.url
            except ValueError:
                return None
        return None

    class Meta:
        model = Subscription
        fields = [
            'id', 'subscription_type', 'subscription_type_name', 
            'batch', 'batch_name',
            'duration', 'duration_unit', 'duration_display',
            'start_date', 'end_date', 'status', 
            'base_amount', 'discount_amount', 'final_amount', 
            'amount_paid', 'balance_amount',
            'is_fully_paid', 'payment_terms', 'installment_count', 
            'installment_period', 'installment_period_unit',
            'installments',
            'member_name', 'member_id_code', 'member_mobile', 'member_photo',
            'days_remaining'
        ]


class SubscriptionListSerializer(serializers.ModelSerializer):
    """Serializer for subscription list including member details"""
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    member_id = serializers.CharField(source='member.member_id', read_only=True)
    branch_name = serializers.SerializerMethodField()
    subscription_type_name = serializers.SerializerMethodField()
    days_remaining = serializers.IntegerField(read_only=True)

    def get_branch_name(self, obj):
        if obj.member and obj.member.branch:
            return obj.member.branch.name
        return "Main Branch"

    def get_subscription_type_name(self, obj):
        return obj.subscription_type.name if obj.subscription_type else "Custom"

    class Meta:
        model = Subscription
        fields = [
            'id', 'member', 'member_id', 'member_name', 'branch_name',
            'subscription_type_name', 'start_date', 'end_date', 
            'status', 'final_amount', 'amount_paid', 'balance_amount',
            'days_remaining', 'is_fully_paid'
        ]


class MemberMobileListSerializer(serializers.ModelSerializer):
    """Optimized serializer for mobile member listing"""
    branch_name = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    active_subscription = serializers.SerializerMethodField()

    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else "Main Branch"

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'full_name', 'mobile_number', 
            'photo', 'membership_status', 'is_active',
            'active_subscription', 'branch', 'branch_name', 
            'access_expiry_date', 'access_enabled', 
            'is_access_blocked', 'manual_access_expiry',
            'subscription_count'
        ]

    def get_active_subscription(self, obj):
        """Return basic info about current active subscription if any"""
        sub = obj.current_subscription
        if sub:
            return {
                'id': sub.id,
                'end_date': sub.end_date,
                'days_remaining': sub.days_remaining,
                'subscription_type_name': sub.subscription_type.name if sub.subscription_type else "Custom"
            }
        return None

    subscription_count = serializers.SerializerMethodField()

    def get_subscription_count(self, obj):
        return obj.subscriptions.count()

class MemberDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for a member including all subscriptions"""
    branch_name = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    subscriptions = SubscriptionSerializer(many=True, read_only=True)
    age = serializers.IntegerField(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else "Main Branch"

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'first_name', 'last_name', 'full_name',
            'mobile_number', 'email', 'date_of_birth', 'age', 'gender',
            'address', 'photo', 'id_proof', 'membership_status',
            'is_active', 'height', 'weight', 'bmi', 'blood_group',
            'medical_history', 'emergency_contact_name', 'emergency_contact_number',
            'registration_date', 'branch', 'branch_name', 'subscriptions',
            'access_expiry_date', 'access_enabled',
            'is_access_blocked', 'manual_access_expiry'
        ]

class MemberStatsSerializer(serializers.Serializer):
    """Serializer for member dashboard statistics"""
    total_members = serializers.IntegerField()
    active_members = serializers.IntegerField()
    expiring_members = serializers.IntegerField()
    expired_members = serializers.IntegerField()
