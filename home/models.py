from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
import uuid


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


def generate_license_key():
    """Generate a unique 20-character license key"""
    return str(uuid.uuid4()).replace('-', '').upper()[:20]


class LicenseKey(models.Model):
    """Model for managing license keys"""
    key = models.CharField(max_length=100, unique=True, editable=False)
    assigned_to = models.OneToOneField(
        'GymOffice', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_license'
    )
    valid_until = models.DateField(blank=True, null=True, editable=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Feature flags
    fetcher_multi_branch = models.BooleanField(default=False)
    fetcher_food_log = models.BooleanField(default=False)
    fetcher_attendance = models.BooleanField(default=True)
    fetcher_payment = models.BooleanField(default=True)
    
    # Limits
    max_branches = models.IntegerField(default=1, help_text="Maximum branches allowed (0 = unlimited)")
    max_members = models.IntegerField(default=0, help_text="Maximum members allowed (0 = unlimited)")
    max_staff = models.IntegerField(default=5, help_text="Maximum staff allowed (0 = unlimited)")
    
    # Additional features stored as JSON for flexibility
    features = models.JSONField(default=dict, blank=True, help_text="Additional features in JSON format")

    class Meta:
        verbose_name = "License Key"
        verbose_name_plural = "License Keys"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if is_new:
            self.key = generate_license_key()
            self.valid_until = timezone.now().date() + timedelta(days=15)

        super().save(*args, **kwargs)

    def has_feature(self, feature_name):
        """Check if license has a specific feature"""
        # Check boolean fields first
        if hasattr(self, f'fetcher_{feature_name}'):
            return getattr(self, f'fetcher_{feature_name}')
        # Check JSON features
        return self.features.get(feature_name, False)

    def is_valid(self):
        """Check if license is still valid"""
        if not self.valid_until:
            return False
        return date.today() <= self.valid_until

    def __str__(self):
        status = "Valid" if self.is_valid() else "Expired"
        return f"{self.key} - {status}"


class GymOffice(models.Model):
    """Model representing a gym office/headquarters"""
    name = models.CharField(max_length=255)
    address = models.TextField()
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    logo = models.FileField(upload_to='gym_logos/', null=True, blank=True)
    
    # License and subscription fields
    license_key = models.OneToOneField(
        LicenseKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gym_office'
    )
    is_active = models.BooleanField(default=True)
    
    # Trial period
    trial_started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    
    # Subscription
    subscription_started_at = models.DateTimeField(blank=True, null=True)
    subscription_valid_until = models.DateField(null=True, blank=True)
    
    # Payment tracking
    razorpay_customer_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gym Office"
        verbose_name_plural = "Gym Offices"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['subscription_valid_until']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):
        # Set trial end date if new instance
        if not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timedelta(days=15)
        
        super().save(*args, **kwargs)

    def is_trial_active(self):
        """Check if trial period is still active"""
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at

    def is_subscription_active(self):
        """Check if subscription is active"""
        if not self.subscription_valid_until:
            return False
        return date.today() <= self.subscription_valid_until

    def can_access_service(self):
        """Check if gym can access the application"""
        return self.is_active and (self.is_trial_active() or self.is_subscription_active())

    def can_create_branch(self):
        """Check if gym can create more branches based on license"""
        if not self.license_key:
            return False
        
        if not self.license_key.fetcher_multi_branch:
            return self.gym_branches.filter(is_active=True).count() < 1
        
        max_branches = self.license_key.max_branches
        if max_branches == 0:  # Unlimited
            return True
        
        return self.gym_branches.filter(is_active=True).count() < max_branches

    def get_active_branches_count(self):
        """Get count of active branches"""
        return self.gym_branches.filter(is_active=True).count()

    def extend_subscription(self, months=12, payment_transaction=None):
        """Extend subscription for specified months"""
        # Determine the start date for extension
        if self.is_subscription_active():
            start_date = self.subscription_valid_until
            new_end_date = start_date + relativedelta(months=months)
        elif self.is_trial_active():
            start_date = self.trial_ends_at.date()
            new_end_date = start_date + relativedelta(months=months)
        else:
            start_date = date.today()
            new_end_date = start_date + relativedelta(months=months)
        
        # Update gym subscription
        self.subscription_valid_until = new_end_date
        if not self.subscription_started_at:
            self.subscription_started_at = timezone.now()
        
        self.save()
        
        # Create subscription history
        SubscriptionHistory.objects.create(
            gym=self,
            payment_transaction=payment_transaction,
            started_at=timezone.now(),
            expires_at=timezone.datetime.combine(
                new_end_date, 
                timezone.datetime.min.time()
            ).replace(tzinfo=timezone.get_current_timezone()),
            previous_expires_at=timezone.datetime.combine(
                start_date, 
                timezone.datetime.min.time()
            ).replace(tzinfo=timezone.get_current_timezone()) if start_date != date.today() else None,
            plan_name=f"{months} Month{'s' if months > 1 else ''} Extension",
            amount_paid=payment_transaction.amount if payment_transaction else 0,
            is_extension=True
        )
        
        return new_end_date

    def get_subscription_status(self):
        """Get detailed subscription status"""
        status = {
            'can_access': self.can_access_service(),
            'is_trial_active': self.is_trial_active(),
            'is_subscription_active': self.is_subscription_active(),
            'trial_ends_at': self.trial_ends_at,
            'subscription_ends_at': self.subscription_valid_until,
            'days_remaining': None,
            'status_text': 'Inactive'
        }
        
        if self.is_subscription_active():
            days_remaining = (self.subscription_valid_until - date.today()).days
            status['days_remaining'] = days_remaining
            status['status_text'] = f'Active ({days_remaining} days remaining)'
        elif self.is_trial_active():
            days_remaining = (self.trial_ends_at.date() - date.today()).days
            status['days_remaining'] = days_remaining
            status['status_text'] = f'Trial ({days_remaining} days remaining)'
        elif not self.is_active:
            status['status_text'] = 'Account Disabled'
        else:
            status['status_text'] = 'Subscription Expired'
        
        return status

    def user_has_permission(self, user, permission=None):
        """Check if user has permission to manage this gym"""
        if user.role == 'admin':
            return True
        if user.role == 'gym_admin' and user.gym == self:
            return True
        return False

    def __str__(self):
        return self.name


class GymBranch(models.Model):
    """Model representing a gym branch"""
    name = models.CharField(max_length=255)
    address = models.TextField()
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    gym = models.ForeignKey(
        GymOffice, 
        on_delete=models.CASCADE, 
        related_name='gym_branches'
    )
    is_active = models.BooleanField(default=True)
    
    # Branch admin/manager
    created_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_branches'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gym Branch"
        verbose_name_plural = "Gym Branches"
        ordering = ['gym', 'name']
        indexes = [
            models.Index(fields=['gym', 'is_active']),
            models.Index(fields=['email']),
        ]

    def clean(self):
        """Validate branch creation based on license"""
        super().clean()
        
        # Check if gym can create branch (only for new branches)
        if self._state.adding and not self.gym.can_create_branch():
            raise ValidationError(
                "Cannot create new branch. License limit reached or multi-branch feature not enabled."
            )

    def get_staff_count(self):
        """Get count of staff in this branch"""
        return self.users.filter(role__in=['staff', 'trainer'], is_active=True).count()

    def __str__(self):
        return f"{self.gym.name} - {self.name}"


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom user model with role-based access"""
    USER_ROLES = (
        ('admin', 'Super Admin'),
        ('gym_admin', 'Gym Owner/Admin'),
        ('branch_admin', 'Branch Manager'),
        ('staff', 'Staff'),
        ('trainer', 'Trainer'),
    )

    username = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(unique=True, verbose_name='Email Address')
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    
    # Role and organization structure
    role = models.CharField(max_length=20, choices=USER_ROLES)
    gym = models.ForeignKey(
        'GymOffice', 
        on_delete=models.CASCADE,
        null=True, 
        blank=True,
        related_name='users'
    )
    branch = models.ForeignKey(
        'GymBranch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    # Status fields
    is_active = models.BooleanField(default=True, verbose_name='Active')
    is_staff = models.BooleanField(default=False, verbose_name='Staff Status')
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone_number']
    
    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['gym', 'role']),
            models.Index(fields=['branch', 'role']),
        ]

    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Super admin shouldn't have gym or branch
        if self.role == 'admin' and (self.gym or self.branch):
            raise ValidationError("Super admin cannot be assigned to a gym or branch")
        
        # Gym admin must have gym but not branch
        if self.role == 'gym_admin':
            if not self.gym:
                raise ValidationError("Gym admin must be assigned to a gym")
            if self.branch:
                raise ValidationError("Gym admin cannot be assigned to a specific branch")
        
        # Branch admin, staff, and trainers must have both gym and branch
        if self.role in ['branch_admin', 'staff', 'trainer']:
            if not self.gym:
                raise ValidationError(f"{self.get_role_display()} must be assigned to a gym")
            if not self.branch:
                raise ValidationError(f"{self.get_role_display()} must be assigned to a branch")
            # Verify branch belongs to gym
            if self.branch and self.gym and self.branch.gym != self.gym:
                raise ValidationError("Branch must belong to the assigned gym")

    def save(self, *args, **kwargs):
        # Auto-generate username if not provided
        if not self.username:
            self.username = self.email.split('@')[0]
        
        # Set is_staff for admin, gym_admin, and branch_admin
        if self.role in ['admin', 'gym_admin', 'branch_admin']:
            self.is_staff = True
        
        self.full_clean()  # Run validation
        super().save(*args, **kwargs)

    def get_full_name(self):
        """Return the username"""
        return self.username or self.email.split('@')[0]
    
    def get_short_name(self):
        """Return the short name for the user"""
        return self.username or self.email.split('@')[0]

    def can_manage_gym(self, gym=None):
        """Check if user can manage a specific gym"""
        if self.role == 'admin':
            return True
        if self.role == 'gym_admin':
            return self.gym == gym if gym else True
        return False

    def can_manage_branch(self, branch=None):
        """Check if user can manage a specific branch"""
        if self.role == 'admin':
            return True
        if self.role == 'gym_admin' and branch:
            return branch.gym == self.gym
        if self.role == 'branch_admin':
            return self.branch == branch if branch else True
        return False

    def get_accessible_branches(self):
        """Get all branches this user can access"""
        if self.role == 'admin':
            return GymBranch.objects.all()
        elif self.role == 'gym_admin' and self.gym:
            return self.gym.gym_branches.all()
        elif self.role in ['branch_admin', 'staff', 'trainer'] and self.branch:
            return GymBranch.objects.filter(id=self.branch.id)
        return GymBranch.objects.none()

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"


class SubscriptionHistory(models.Model):
    """Track subscription history and payments"""
    gym = models.ForeignKey(
        GymOffice, 
        on_delete=models.CASCADE, 
        related_name='subscription_history'
    )
    payment_transaction = models.ForeignKey(
        'PaymentTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    previous_expires_at = models.DateTimeField(null=True, blank=True)
    plan_name = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    is_extension = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Subscription History"
        verbose_name_plural = "Subscription Histories"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.gym.name} - {self.plan_name} ({self.started_at.date()} to {self.expires_at.date()})"


class PaymentTransaction(models.Model):
    """Track payment transactions"""
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    gym = models.ForeignKey(
        GymOffice,
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Payment gateway details
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    # Additional info
    plan_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gym', 'status']),
            models.Index(fields=['razorpay_order_id']),
        ]

    def __str__(self):
        return f"{self.gym.name} - ₹{self.amount} ({self.get_status_display()})"