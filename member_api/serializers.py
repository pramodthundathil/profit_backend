from rest_framework import serializers
from members.models import Member, Subscription, SubscriptionInstallment
from payments.models import Payment

from .models import MemberAppSettings


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class MemberLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False, help_text="Member ID or email address")
    email = serializers.CharField(required=False, help_text="Older app versions send the email here")
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        identifier = (data.get('identifier') or data.get('email') or '').strip()
        if not identifier:
            raise serializers.ValidationError({'identifier': 'Enter your Member ID or email address.'})
        data['identifier'] = identifier
        return data


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class MemberAppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberAppSettings
        fields = list(MemberAppSettings.FEATURE_FIELDS) + ['updated_at']
        read_only_fields = ['updated_at']


class MemberSummarySerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'member_id', 'first_name', 'last_name', 'full_name', 'email', 'photo', 'gym_name', 'branch_name']


class BulkEnableSerializer(serializers.Serializer):
    member_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=False)
    all_eligible = serializers.BooleanField(default=False)

    def validate(self, data):
        if not data.get('member_ids') and not data['all_eligible']:
            raise serializers.ValidationError('Send member_ids or set all_eligible to true.')
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
        ref_name = 'MemberApiSubscriptionInstallment'  # distinct from members.serializers in the API docs
        fields = ['id', 'installment_number', 'due_date', 'amount', 'status']


class SubscriptionSerializer(serializers.ModelSerializer):
    type_name = serializers.CharField(source='subscription_type.name', read_only=True, default="Custom")
    batch_name = serializers.CharField(source='batch.name', read_only=True, allow_null=True)
    installments = SubscriptionInstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        ref_name = 'MemberApiSubscription'  # distinct from members.serializers in the API docs
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
