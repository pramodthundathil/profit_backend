from rest_framework import serializers
from members.models import Member, Subscription, SubscriptionInstallment
from payments.models import Payment
from home.models import CustomUser

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

class EmailPasswordLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'receipt_number', 'amount', 'payment_date', 
            'payment_method', 'status', 'is_installment', 'installment_number'
        ]

class SubscriptionInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionInstallment
        fields = ['id', 'installment_number', 'due_date', 'amount', 'status']

class SubscriptionSerializer(serializers.ModelSerializer):
    type_name = serializers.CharField(source='subscription_type.name', read_only=True, default="Custom")
    batch_name = serializers.CharField(source='batch.name', read_only=True, allow_null=True)
    installments = SubscriptionInstallmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'type_name', 'duration', 'duration_unit', 
            'start_date', 'end_date', 'final_amount', 'amount_paid', 
            'balance_amount', 'status', 'is_fully_paid', 'installments',
            'batch_name', 'includes_personal_training', 'personal_training_sessions',
            'includes_diet_plan', 'includes_locker', 'locker_number',
            'freeze_allowed', 'freeze_days_allowed', 'freeze_days_used'
        ]

class MemberProfileSerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    subscriptions = SubscriptionSerializer(many=True, read_only=True)
    payments = PaymentHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'first_name', 'last_name', 'email', 'mobile_number',
            'gender', 'date_of_birth', 'height', 'weight', 'blood_group',
            'membership_status', 'access_enabled', 'access_expiry_date',
            'access_token', 'gym_name', 'branch_name', 'photo', 
            'subscriptions', 'payments'
        ]
