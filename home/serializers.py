from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    CustomUser, GymOffice, GymBranch, LicenseKey,
    SubscriptionHistory, PaymentTransaction, HikConfigurationDb
)


class LicenseKeySerializer(serializers.ModelSerializer):
    """Serializer for License Key"""
    is_valid_license = serializers.SerializerMethodField()
    
    class Meta:
        model = LicenseKey
        fields = [
            'id', 'key', 'valid_until', 'is_used', 'created_at',
            'fetcher_multi_branch', 'fetcher_food_log', 'fetcher_attendance',
            'fetcher_payment', 'max_branches', 'max_members', 'max_staff',
            'features', 'is_valid_license'
        ]
        read_only_fields = ['key', 'created_at', 'is_valid_license']
    
    def get_is_valid_license(self, obj):
        return obj.is_valid()


class GymOfficeSerializer(serializers.ModelSerializer):
    """Serializer for Gym Office"""
    subscription_status = serializers.SerializerMethodField()
    active_branches_count = serializers.SerializerMethodField()
    license_details = LicenseKeySerializer(source='license_key', read_only=True)
    
    class Meta:
        model = GymOffice
        fields = [
            'id', 'name', 'address', 'email', 'phone', 'logo',
            'is_active', 'trial_started_at', 'trial_ends_at',
            'subscription_started_at', 'subscription_valid_until',
            'created_at', 'updated_at', 'subscription_status',
            'active_branches_count', 'license_details'
        ]
        read_only_fields = [
            'trial_started_at', 'trial_ends_at', 'created_at',
            'updated_at', 'subscription_status', 'active_branches_count'
        ]
    
    def get_subscription_status(self, obj):
        return obj.get_subscription_status()
    
    def get_active_branches_count(self, obj):
        return obj.get_active_branches_count()


class GymOfficeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Gym Office with admin"""
    admin_email = serializers.EmailField(write_only=True)
    admin_phone = serializers.CharField(write_only=True, max_length=17)
    admin_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    admin_username = serializers.CharField(write_only=True, required=False)
    license_key_code = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = GymOffice
        fields = [
            'id', 'name', 'address', 'email', 'phone', 'logo',
            'admin_email', 'admin_phone', 'admin_password', 'admin_username',
            'license_key_code'
        ]
    
    def validate_admin_password(self, value):
        """Validate password strength"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate_admin_email(self, value):
        """Check if admin email already exists"""
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def validate_license_key_code(self, value):
        """Validate license key if provided"""
        if value:
            try:
                license_key = LicenseKey.objects.get(key=value, is_used=False)
                if not license_key.is_valid():
                    raise serializers.ValidationError("This license key has expired.")
            except LicenseKey.DoesNotExist:
                raise serializers.ValidationError("Invalid or already used license key.")
        return value
    
    def create(self, validated_data):
        # Extract admin data
        admin_email = validated_data.pop('admin_email')
        admin_phone = validated_data.pop('admin_phone')
        admin_password = validated_data.pop('admin_password')
        admin_username = validated_data.pop('admin_username', None)
        license_key_code = validated_data.pop('license_key_code', None)
        
        # Handle license key
        license_key = None
        if license_key_code:
            license_key = LicenseKey.objects.get(key=license_key_code)
        
        # Create gym office
        gym = GymOffice.objects.create(
            license_key=license_key,
            **validated_data
        )
        
        # Mark license as used
        if license_key:
            license_key.is_used = True
            license_key.assigned_to = gym
            license_key.save()
        
        # Create gym admin
        admin = CustomUser.objects.create_user(
            email=admin_email,
            password=admin_password,
            phone_number=admin_phone,
            username=admin_username,
            role='gym_admin',
            gym=gym,
            is_staff=True
        )
        
        return gym


class GymBranchSerializer(serializers.ModelSerializer):
    """Serializer for Gym Branch"""
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    staff_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = GymBranch
        fields = [
            'id', 'name', 'address', 'email', 'phone', 'gym', 'gym_name',
            'is_active', 'created_by', 'created_by_name', 'staff_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'staff_count']
    
    def get_staff_count(self, obj):
        return obj.get_staff_count()
    
    def validate(self, data):
        """Validate branch creation"""
        request = self.context.get('request')
        user = request.user if request else None
        
        # For creation
        if not self.instance:
            gym = data.get('gym')
            
            # Check if user can create branch in this gym
            if user and user.role == 'gym_admin' and user.gym != gym:
                raise serializers.ValidationError("You can only create branches in your own gym.")
            
            # Check if gym can create more branches
            if gym and not gym.can_create_branch():
                raise serializers.ValidationError(
                    "Cannot create new branch. License limit reached or multi-branch feature not enabled."
                )
        
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class CustomUserSerializer(serializers.ModelSerializer):
    """Serializer for User listing and details"""
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'phone_number', 'role', 'role_display',
            'gym', 'gym_name', 'branch', 'branch_name', 'is_active',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users"""
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone_number', 'password', 'password_confirm',
            'role', 'gym', 'branch', 'is_active'
        ]
    
    def validate_password(self, value):
        """Validate password strength"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        """Validate user data"""
        request = self.context.get('request')
        user = request.user if request else None
        
        # Check password match
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        
        # Role-based validation
        role = data.get('role')
        gym = data.get('gym')
        branch = data.get('branch')
        
        # Super admin cannot create other super admins
        if role == 'admin':
            raise serializers.ValidationError({"role": "Cannot create super admin users."})
        
        # Validate gym assignment based on current user
        if user and user.role == 'gym_admin':
            if gym != user.gym:
                raise serializers.ValidationError({"gym": "You can only create users for your own gym."})
        
        # Validate branch assignment based on current user
        if user and user.role == 'branch_admin':
            if branch != user.branch:
                raise serializers.ValidationError({"branch": "You can only create users for your own branch."})
        
        # Gym admin should have gym but not branch
        if role == 'gym_admin':
            if not gym:
                raise serializers.ValidationError({"gym": "Gym admin must be assigned to a gym."})
            if branch:
                raise serializers.ValidationError({"branch": "Gym admin cannot be assigned to a specific branch."})
        
        # Branch-level roles must have both gym and branch
        if role in ['branch_admin', 'staff', 'trainer']:
            if not gym:
                raise serializers.ValidationError({"gym": f"{role} must be assigned to a gym."})
            if not branch:
                raise serializers.ValidationError({"branch": f"{role} must be assigned to a branch."})
            # Verify branch belongs to gym
            if branch and gym and branch.gym != gym:
                raise serializers.ValidationError({"branch": "Branch must belong to the assigned gym."})
        
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(password=password, **validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users"""
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone_number', 'role',
            'gym', 'branch', 'is_active'
        ]
    
    def validate(self, data):
        """Validate user update"""
        request = self.context.get('request')
        user = request.user if request else None
        instance = self.instance
        
        # Cannot change to admin role
        if data.get('role') == 'admin' and instance.role != 'admin':
            raise serializers.ValidationError({"role": "Cannot change user to super admin."})
        
        # Gym admin can only update users in their gym
        if user and user.role == 'gym_admin':
            if data.get('gym') and data.get('gym') != user.gym:
                raise serializers.ValidationError({"gym": "You can only manage users in your own gym."})
        
        # Branch admin can only update users in their branch
        if user and user.role == 'branch_admin':
            if data.get('branch') and data.get('branch') != user.branch:
                raise serializers.ValidationError({"branch": "You can only manage users in your own branch."})
        
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        """Validate new password strength"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        """Validate password match"""
        if data.get('new_password') != data.get('new_password_confirm'):
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """Serializer for Subscription History"""
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    
    class Meta:
        model = SubscriptionHistory
        fields = [
            'id', 'gym', 'gym_name', 'payment_transaction', 'started_at',
            'expires_at', 'previous_expires_at', 'plan_name', 'amount_paid',
            'is_extension', 'created_at'
        ]
        read_only_fields = ['created_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Payment Transaction"""
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'gym', 'gym_name', 'amount', 'status', 'status_display',
            'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature',
            'plan_name', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class GymRegistrationSerializer(serializers.Serializer):
    """Serializer for complete gym registration"""
    # Gym details
    gym_name = serializers.CharField(max_length=255)
    gym_address = serializers.CharField()
    gym_email = serializers.EmailField()
    gym_phone = serializers.CharField(max_length=17)
    gym_logo = serializers.FileField(required=False)
    
    # Admin details
    admin_username = serializers.CharField(max_length=100, required=False)
    admin_email = serializers.EmailField()
    admin_phone = serializers.CharField(max_length=17)
    admin_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    admin_password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    # License (optional)
    license_key = serializers.CharField(required=False)
    
    def validate_gym_email(self, value):
        if GymOffice.objects.filter(email=value).exists():
            raise serializers.ValidationError("Gym with this email already exists.")
        return value
    
    def validate_admin_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def validate_admin_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        if data.get('admin_password') != data.get('admin_password_confirm'):
            raise serializers.ValidationError({"admin_password_confirm": "Passwords do not match."})
        
        if data.get('license_key'):
            try:
                license_obj = LicenseKey.objects.get(key=data['license_key'], is_used=False)
                if not license_obj.is_valid():
                    raise serializers.ValidationError({"license_key": "This license key has expired."})
            except LicenseKey.DoesNotExist:
                raise serializers.ValidationError({"license_key": "Invalid or already used license key."})
        
        return data
    
    def create(self, validated_data):
        # Extract data
        admin_password = validated_data.pop('admin_password')
        validated_data.pop('admin_password_confirm')
        
        license_key_code = validated_data.pop('license_key', None)
        license_obj = None
        if license_key_code:
            license_obj = LicenseKey.objects.get(key=license_key_code)
        
        # Create gym
        gym = GymOffice.objects.create(
            name=validated_data['gym_name'],
            address=validated_data['gym_address'],
            email=validated_data['gym_email'],
            phone=validated_data['gym_phone'],
            logo=validated_data.get('gym_logo'),
            license_key=license_obj
        )
        
        # Mark license as used
        if license_obj:
            license_obj.is_used = True
            license_obj.assigned_to = gym
            license_obj.save()
        
        # Create admin
        admin = CustomUser.objects.create_user(
            email=validated_data['admin_email'],
            password=admin_password,
            phone_number=validated_data['admin_phone'],
            username=validated_data.get('admin_username'),
            role='gym_admin',
            gym=gym,
            is_staff=True
        )
        
        return {
            'gym': gym,
            'admin': admin
        }


class HikConfigurationDbSerializer(serializers.ModelSerializer):
    """
    Serializer for HikVision Configuration
    """
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    branch_name = serializers.CharField(source='gym_branch.name', read_only=True)

    class Meta:
        model = HikConfigurationDb
        fields = [
            'id', 'gym', 'gym_name', 'gym_branch', 'branch_name',
            'middleware_url', 'middleware_port', 'device_ip',
            'device_port', 'device_username', 'device_password'
        ]

    def validate(self, data):
        """
        Validate configuration
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        # Check permissions and constraints
        gym = data.get('gym')
        gym_branch = data.get('gym_branch')
        
        if not gym and not gym_branch:
             # If partial update, we might not have these fields, but model validation handles required check.
             # However, for create, we need at least one.
             if not self.instance:
                 raise serializers.ValidationError("Either gym or gym_branch must be provided.")

        # If User is Branch Manager, they can only assign to their branch
        if user and user.role == 'branch_admin':
            if gym:
                raise serializers.ValidationError({"gym": "Branch Manager cannot configure for the entire Gym Office."})
            if gym_branch and gym_branch != user.branch:
                # This might be redundant if we force it in perform_create but good for validation
                 raise serializers.ValidationError({"gym_branch": "You can only configure your own branch."})

        # If User is Gym Admin, they can assign to gym or their branches
        if user and user.role == 'gym_admin':
            if gym and gym != user.gym:
                 raise serializers.ValidationError({"gym": "You can only configure your own gym."})
            if gym_branch and gym_branch.gym != user.gym:
                 raise serializers.ValidationError({"gym_branch": "You can only configure branches within your gym."})

        return data
