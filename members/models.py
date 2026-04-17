from django.db import models
import uuid
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from decimal import Decimal
from utils.models import  Batch_DB, TypeSubscription, SubscriptionPeriod   
from home.models  import GymOffice, GymBranch

class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Soft delete for queryset"""
        return super().update(is_deleted=True)

    def hard_delete(self):
        """Actual deletion from database"""
        return super().delete()

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


# ============================================================================
# MEMBER MODEL
# ============================================================================

class Member(models.Model):
    """Gym member/customer"""
    # Basic Info
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='members')
    branch = models.ForeignKey(
        GymBranch, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='members',
        help_text="Primary branch"
    )
    
    member_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Personal Details
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=(("Male", "Male"), ("Female", "Female"), ("Other", "Other"))
    )
    
    # Contact
    mobile_number = models.CharField(max_length=20)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(max_length=500, null=True, blank=True)
    
    # Health Information
    height = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Height in cm"
    )
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Weight in kg"
    )
    blood_group = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=(
            ("A+", "A+"), ("A-", "A-"),
            ("B+", "B+"), ("B-", "B-"),
            ("AB+", "AB+"), ("AB-", "AB-"),
            ("O+", "O+"), ("O-", "O-")
        )
    )
    medical_history = models.TextField(max_length=2000, null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=255, null=True, blank=True)
    emergency_contact_number = models.CharField(max_length=20, null=True, blank=True)
    
    # Documents
    photo = models.ImageField(upload_to='members/photos/', null=True, blank=True)
    id_proof = models.FileField(upload_to='members/id_proofs/', null=True, blank=True)
    
    # Dates
    registration_date = models.DateField(default=timezone.now)
    date_added = models.DateTimeField(auto_now_add=True)
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Overall account status (can be disabled by admin)"
    )
    membership_status = models.CharField(
        max_length=20,
        choices=(
            ("Active", "Active"),
            ("Expired", "Expired"),
            ("Suspended", "Suspended"),
            ("Cancelled", "Cancelled")
        ),
        default="Active"
    )
    
    # Access Control
    access_enabled = models.BooleanField(
        default=False,
        help_text="Can access gym (based on valid subscription + payment)"
    )
    access_token = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        unique=True,
        help_text="RFID/Barcode/QR for gate access"
    )
    
    access_expiry_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Highest access date across all active/paid subscriptions (or manual extension)"
    )
    
    is_access_blocked = models.BooleanField(
        default=False,
        help_text="Manually block access regardless of subscription status"
    )
    
    manual_access_expiry = models.DateField(
        null=True, 
        blank=True,
        help_text="Manual access extension date"
    )
    
    # Notes
    notes = models.TextField(blank=True, null=True, help_text="Admin notes about member")
    
    risk_medical = models.BooleanField(default=False)
    public_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    is_deleted = models.BooleanField(default=False)
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        unique_together = ['gym', 'mobile_number']
        ordering = ['-date_added']
        indexes = [
            models.Index(fields=['gym', 'member_id']),
            models.Index(fields=['gym', 'mobile_number']),
            models.Index(fields=['access_token']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.member_id:
            # Generate unique member ID
            last_member = Member.all_objects.filter(gym=self.gym).order_by('-id').first()
            if last_member and last_member.member_id:
                try:
                    last_number = int(last_member.member_id.split('-')[-1])
                    new_number = last_number + 1
                except:
                    new_number = 1
            else:
                new_number = 1
            
            # Generate code from gym name (first 3 letters or default GYM)
            gym_code = (self.gym.name[:3].upper() if self.gym.name else "GYM")
            self.member_id = f"{gym_code}-{new_number:05d}"
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Soft delete member and cascade to subscriptions"""
        self.is_deleted = True
        self.is_active = False
        self.membership_status = 'Cancelled'
        self.save()
        
        # Soft delete all subscriptions
        for subscription in self.subscriptions.all():
            subscription.delete()
    
    def update_membership_status(self):
        """Update membership status based on active subscriptions"""
        today = timezone.now().date()
        
        # Check for any subscriptions that are not cancelled
        has_subscriptions = self.subscriptions.exclude(status='Cancelled').exists()
        
        if not has_subscriptions:
            self.membership_status = 'Active' # Default for new members without plans yet
            self.access_enabled = False
            self.access_expiry_date = None
        else:
            # Check for active subscriptions (based on date)
            active_exists = self.subscriptions.filter(
                status='Active',
                end_date__gte=today
            ).exists()
            
            if active_exists or self.access_enabled:
                self.membership_status = 'Active'
            else:
                self.membership_status = 'Expired'
            
            # Recalculate access if needed (optional since access_enabled was already checked)
            # but usually it's better to update access status first then status
            self.update_access_status()
            
            # Ensure status if access was just updated to enabled
            if self.access_enabled:
                self.membership_status = 'Active'
        
        self.save()
    
    def update_access_status(self):
        """
        Identify the highest access expiry date across all active 
        and fully paid subscriptions, or manual extension.
        """
        if self.is_access_blocked:
            self.access_enabled = False
            self.save(update_fields=['access_enabled'])
            return

        today = timezone.now().date()
        
        # 1. Start with manual extension if valid (Ensure it's a date object)
        manual_expiry = self.manual_access_expiry
        if isinstance(manual_expiry, str):
            from datetime import datetime
            try:
                manual_expiry = datetime.strptime(manual_expiry, '%Y-%m-%d').date()
            except ValueError:
                manual_expiry = None
                
        max_expiry = manual_expiry if manual_expiry and manual_expiry >= today else None
        
        # 2. Get all subscriptions that are Active (Paid or Partially Paid) and Not Expired
        active_subs = self.subscriptions.filter(
            status='Active',
            end_date__gte=today
        ).order_by('-end_date')
        
        if active_subs.exists():
            sub_expiry = active_subs.first().end_date
            if not max_expiry or sub_expiry > max_expiry:
                max_expiry = sub_expiry

        if max_expiry:
            self.access_expiry_date = max_expiry
            self.access_enabled = True
        else:
            self.access_expiry_date = None
            self.access_enabled = False
        
        self.save(update_fields=['access_expiry_date', 'access_enabled'])
    
    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def bmi(self):
        """Calculate BMI"""
        if self.height and self.weight:
            height_m = float(self.height) / 100
            return round(float(self.weight) / (height_m ** 2), 2)
        return None
    
    @property
    def current_subscription(self):
        """Get current active subscription"""
        today = timezone.now().date()
        return self.subscriptions.filter(
            status='Active',
            start_date__lte=today,
            end_date__gte=today
        ).first()
    
    def __str__(self):
        return f"{self.member_id} - {self.full_name}"


# ============================================================================
# CUSTOM SUBSCRIPTION MODEL
# ============================================================================

class Subscription(models.Model):
    """Fully customizable subscription for each member"""
    
    # Member Info
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="subscriptions")
    
    # Subscription Details - All Customizable
    subscription_type = models.ForeignKey(
        TypeSubscription, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        help_text="Type of subscription (optional category)"
    )

    # Access Control
    access_branch = models.ForeignKey(
        GymBranch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='branch_subscriptions',
        help_text="Branch where this subscription grants access (None for HQ/All)"
    )
    is_hq_access = models.BooleanField(
        default=False,
        help_text="Grants access to headquarters/all branches"
    )
    
    # Custom Period
    duration = models.PositiveIntegerField(help_text="Number of days/weeks/months")
    duration_unit = models.CharField(
        max_length=20,
        choices=(
            ("Days", "Days"),
            ("Weeks", "Weeks"),
            ("Months", "Months"),
            ("Years", "Years")
        ),
        default="Days"
    )
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Batch Assignment
    batch = models.ForeignKey(
        Batch_DB, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="subscriptions"
    )
    batch_flexible = models.BooleanField(
        default=False,
        help_text="Member can attend any batch"
    )
    
    # Custom Pricing
    base_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Base subscription amount"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Discount percentage"
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Fixed discount amount"
    )
    final_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final amount after discounts"
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total discount applied via offers"
    )
    balance_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Additional Features (Custom per subscription)
    includes_personal_training = models.BooleanField(default=False)
    personal_training_sessions = models.PositiveIntegerField(
        default=0,
        help_text="Number of PT sessions included"
    )
    includes_diet_plan = models.BooleanField(default=False)
    includes_locker = models.BooleanField(default=False)
    locker_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Freeze Options
    freeze_allowed = models.BooleanField(default=False)
    freeze_days_allowed = models.PositiveIntegerField(
        default=0,
        help_text="Number of days member can freeze subscription"
    )
    freeze_days_used = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=(
            ("Active", "Active"),
            ("Expired", "Expired"),
            ("Cancelled", "Cancelled"),
            ("Suspended", "Suspended"),
            ("Frozen", "Frozen")
        ),
        default="Active"
    )
    is_fully_paid = models.BooleanField(default=False)
    
    # Payment Terms
    payment_terms = models.CharField(
        max_length=50,
        choices=(
            ("Full", "Full Payment"),
            ("Installment", "Installment"),
            ("Monthly", "Monthly")
        ),
        default="Full"
    )
    installment_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of installments if applicable"
    )
    installment_period = models.PositiveIntegerField(
        default=1,
        help_text="Frequency of installments (e.g., 1, 2)"
    )
    installment_period_unit = models.CharField(
        max_length=20,
        choices=(
            ("Days", "Days"),
            ("Weeks", "Weeks"),
            ("Months", "Months"),
            ("Years", "Years")
        ),
        default="Months",
        help_text="Unit for installment frequency"
    )
    
    # Notes & Metadata
    custom_terms = models.TextField(
        blank=True,
        null=True,
        help_text="Custom terms and conditions for this subscription"
    )
    notes = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['member', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'end_date']),
        ]
    
    @property
    def due_amount(self):
        """Calculate amount due (Total - Paid - Discount)"""
        return max(0, self.final_amount - self.amount_paid - self.discount_amount)

    @property
    def payment_status_label(self):
        """Get payment status label based on total credit"""
        total_credit = self.amount_paid + self.discount_amount
        if total_credit >= self.final_amount:
            return "Paid"
        elif total_credit > 0:
            return "Partial"
        return "Unpaid"

    def save(self, *args, **kwargs):
        # Auto-calculate final amount
        if not self.final_amount or self.final_amount == 0:
            # Apply percentage discount
            percentage_discount = (self.base_amount * self.discount_percentage) / 100
            # Apply fixed discount
            total_discount = percentage_discount + self.discount_amount
            # Calculate final amount
            self.final_amount = max(self.base_amount - total_discount, 0)
        
        super().save(*args, **kwargs)
        
        # Generate installments if applicable and if they don't already exist
        if self.payment_terms in ['Installment', 'Full']:
            if not self.installments.exists():
                self.generate_installments()
            
    def delete(self, *args, **kwargs):
        """Soft delete subscription and permanently delete installments"""
        self.is_deleted = True
        self.status = 'Cancelled'
        self.save()
        
        # Permanently delete installments
        self.installments.all().delete()
    
    def clean(self):
        # Validate batch belongs to same gym
        try:
            if self.batch and self.member and self.batch.gym != self.member.gym:
                raise ValidationError("Batch must belong to the same gym")
        except Member.DoesNotExist:
             # Member might not be assigned yet during creation phase in forms
             pass
        
        # Validate dates
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")
    
    def get_total_days(self):
        """Convert duration to total days"""
        if self.duration_unit == "Days":
            return self.duration
        elif self.duration_unit == "Weeks":
            return self.duration * 7
        elif self.duration_unit == "Months":
            return self.duration * 30
        elif self.duration_unit == "Years":
            return self.duration * 365
        return 0
    
    def update_payment_status(self):
        """Update payment status based on payments and adjust end date based on installments"""
        aggr = self.payments.filter(status='Completed').aggregate(
            total_cash=models.Sum('amount'),
            total_discount=models.Sum('discount_amount')
        )
        
        self.amount_paid = aggr['total_cash'] or Decimal('0')
        self.discount_amount = aggr['total_discount'] or Decimal('0')
        
        # Balance = Total - Cash Paid - Discounts
        self.balance_amount = max(self.final_amount - self.amount_paid - self.discount_amount, 0)
        
        # Status uses total credit (Cash + Discount)
        total_credit = self.amount_paid + self.discount_amount
        # Use a small tolerance (0.01) to handle potential rounding issues with discounts
        self.is_fully_paid = (total_credit >= (self.final_amount - Decimal('0.01')))
        
        # Dynamic End Date Logic based on Installments
        # Only run auto-calculation if not explicitly overridden by a partial payment logic
        if self.payment_terms == 'Installment':
            next_installment = self.installments.exclude(status='Paid').order_by('due_date').first()
            if next_installment:
                if next_installment.status == 'Pending':
                    # Only auto-calculate for Pending. If Partially Paid, we trust the manual expiry set in view.
                    self.end_date = next_installment.due_date - timedelta(days=1)
            else:
                # All paid, set to full term
                self.end_date = self.start_date + timedelta(days=self.get_total_days())
        elif self.payment_terms == 'Full' and self.is_fully_paid:
            # Full Payment also sets end date based on duration
            self.end_date = self.start_date + timedelta(days=self.get_total_days())
        
        self.save(update_fields=['amount_paid', 'discount_amount', 'balance_amount', 'is_fully_paid', 'end_date'])
        
        # When a payment is recorded, also unblock the member if they were restricted
        if self.member.is_access_blocked:
            self.member.is_access_blocked = False
            self.member.save(update_fields=['is_access_blocked'])

        # Update member access
        self.member.update_access_status()
    
    def update_status(self):
        """Auto-update status based on dates"""
        today = timezone.now().date()
        
        if self.status in ['Cancelled', 'Frozen']:
            return  # Don't auto-update these statuses
        
        if not self.end_date:
            return # Cannot auto-update status without end_date
        
        if self.end_date < today:
            self.status = 'Expired'
            self.save(update_fields=['status'])
            self.member.update_membership_status()
        elif self.start_date <= today <= self.end_date:
            if self.status != 'Active':
                self.status = 'Active'
                self.save(update_fields=['status'])
    
    def freeze_subscription(self, days):
        """Freeze subscription for specified days"""
        if not self.freeze_allowed:
            raise ValidationError("Freeze not allowed for this subscription")
        
        if self.freeze_days_used + days > self.freeze_days_allowed:
            raise ValidationError(
                f"Cannot freeze. Only {self.freeze_days_allowed - self.freeze_days_used} days remaining"
            )
        
        self.status = 'Frozen'
        self.freeze_days_used += days
        self.end_date += timedelta(days=days)  # Extend end date
        self.save()
    
    def unfreeze_subscription(self):
        """Unfreeze subscription"""
        if self.status == 'Frozen':
            self.status = 'Active'
            self.save()
    
    
    @property
    def is_expired(self):
        if not self.end_date:
            return False
        return self.end_date < timezone.now().date()
    
    @property
    def days_remaining(self):
        if not self.end_date or self.is_expired:
            return 0
        return (self.end_date - timezone.now().date()).days
    
    def generate_installments(self):
        """Auto-generate installments based on terms"""
        if self.payment_terms == 'Full':
            count = 1
        elif self.payment_terms == 'Installment':
            count = max(1, self.installment_count) # Ensure at least 1
        else:
            return

        # Calculate installment amount based on remaining balance
        current_installments = self.installments.all().order_by('installment_number')
        current_count = current_installments.count()
        
        # We calculate the amount for "not-yet-paid" portions
        remaining_to_split = Decimal(str(self.final_amount)) - Decimal(str(self.amount_paid))
        
        if current_count == 0:
            # First time: divide everything (minus any current payment) by requested count
            amount_per_installment = remaining_to_split / count
        else:
            # Existing: divide current balance by pending installments
            pending_installments = self.installments.exclude(status='Paid')
            pending_count = pending_installments.count()
            if pending_count > 0:
                amount_per_installment = remaining_to_split / pending_count
            else:
                amount_per_installment = Decimal('0')

        # Logic for date calculation
        # If an advance was paid today, the installments start from the next period (offset +1)
        # Otherwise, the first installment is due on the start date (offset 0)
        has_advance = (self.amount_paid > 0)
        
        def calculate_due_date(num, start_date):
            offset = num if has_advance else (num - 1)
            interval = offset * (self.installment_period or 1)
            
            if self.installment_period_unit == 'Days':
                return start_date + timedelta(days=interval)
            elif self.installment_period_unit == 'Weeks':
                return start_date + timedelta(weeks=interval)
            elif self.installment_period_unit == 'Months':
                return start_date + relativedelta(months=interval)
            elif self.installment_period_unit == 'Years':
                return start_date + relativedelta(years=interval)
            else:
                return start_date + relativedelta(months=interval)

        # 1. If installments already exist, DO NOT RECALCULATE AMOUNTS
        # This prevents accidental changes to the payment schedule after payments/discounts are applied.
        if current_count > 0:
            return

        # Clear existing pending installments if re-generating
        self.installments.filter(status='Pending').delete()
        
        # Re-fetch count after deletion
        existing_paid_count = self.installments.count()
        
        # Create new installments for the remaining count
        for i in range(existing_paid_count + 1, count + 1):
             due = calculate_due_date(i, self.start_date)
             
             SubscriptionInstallment.objects.create(
                 subscription=self,
                 installment_number=i,
                 due_date=due,
                 amount=amount_per_installment,
                 status='Pending'
             )

    @property
    def duration_display(self):
        """Human readable duration"""
        return f"{self.duration} {self.duration_unit}"
    
    def __str__(self):
        type_name = self.subscription_type.name if self.subscription_type else "Custom"
        return f"{self.member.full_name} - {type_name} ({self.duration_display}) - {self.start_date} to {self.end_date}"


# ============================================================================
# SUBSCRIPTION FREEZE LOG
# ============================================================================

class SubscriptionFreeze(models.Model):
    """Track subscription freeze periods"""
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="freeze_logs"
    )
    
    freeze_start_date = models.DateField()
    freeze_end_date = models.DateField()
    days_frozen = models.PositiveIntegerField()
    
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unfrozen_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-freeze_start_date']
    
    def __str__(self):
        return f"{self.subscription.member.full_name} - Frozen {self.days_frozen} days"


# ============================================================================
# SUBSCRIPTION INSTALLMENT MODEL
# ============================================================================

class SubscriptionInstallment(models.Model):
    """ Individual installment for a subscription """
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE, 
        related_name="installments"
    )
    
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=(
            ("Pending", "Pending"),
            ("Partially Paid", "Partially Paid"),
            ("Paid", "Paid"),
            ("Overdue", "Overdue")
        ),
        default="Pending"
    )
    
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cash amount paid for this specific installment"
    )
    
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Discount amount applied to this specific installment"
    )
    
    paid_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['due_date']
        unique_together = ['subscription', 'installment_number']
        
    @property
    def remaining_amount(self):
        """Amount remaining for this installment (Total - Paid - Discount)"""
        return max(0, self.amount - self.amount_paid - self.discount_amount)

    def update_payment_status(self):
        """Recalculate amount paid from linked payments and update status"""
        aggr = self.payments.filter(status='Completed').aggregate(
            total_cash=models.Sum('amount'),
            total_discount=models.Sum('discount_amount')
        )
        
        self.amount_paid = aggr['total_cash'] or Decimal('0')
        self.discount_amount = aggr['total_discount'] or Decimal('0')
        
        # Status calculation based on total credit (Cash + Discount)
        total_credit = self.amount_paid + self.discount_amount
        
        # Use a small tolerance (0.01) for rounding safety
        if total_credit >= (self.amount - Decimal('0.01')):
            self.status = 'Paid'
            if not self.paid_date:
                self.paid_date = timezone.now().date()
        elif total_credit > 0:
            self.status = 'Partially Paid'
        else:
            if self.due_date and self.due_date < timezone.now().date():
                self.status = 'Overdue'
            else:
                self.status = 'Pending'
                
        self.save(update_fields=['amount_paid', 'discount_amount', 'status', 'paid_date'])

    def __str__(self):
        return f"{self.subscription} - Installment {self.installment_number} ({self.amount})"

# ============================================================================
# HEALTH & MEDICAL HISTORY MODELS
# ============================================================================

class HealthHistory(models.Model):
    # Link to existing member
    member = models.OneToOneField('Member', on_delete=models.CASCADE, related_name='health_history')
    
    # MANDATORY FIELDS
    # Emergency Contact Information (Mandatory)
    emergency_contact_name = models.CharField(max_length=255)
    emergency_contact_relationship = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=20)
    emergency_contact_address = models.TextField(max_length=500, null=True, blank=True)
    
    # Current Physical Information (Mandatory)
    current_weight = models.FloatField(validators=[MinValueValidator(0)])
    current_height = models.FloatField(validators=[MinValueValidator(0)])  # in cm
    
    # Fitness Goals (Mandatory)
    FITNESS_GOAL_CHOICES = [
        ('weight_loss', 'Weight Loss'),
        ('weight_gain', 'Weight Gain'),
        ('muscle_building', 'Muscle Building'),
        ('cardiovascular', 'Cardiovascular Fitness'),
        ('strength', 'Strength Training'),
        ('flexibility', 'Flexibility & Mobility'),
        ('sports_specific', 'Sports Specific Training'),
        ('general_fitness', 'General Fitness'),
        ('rehabilitation', 'Rehabilitation'),
        ('other', 'Other'),
    ]
    fitness_goal = models.CharField(max_length=50, choices=FITNESS_GOAL_CHOICES)
    fitness_goal_details = models.TextField(max_length=500, null=True, blank=True)
    
    # PT Session Availability (Mandatory)
    AVAILABILITY_CHOICES = [
        ('morning', 'Morning (6 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 6 PM)'),
        ('evening', 'Evening (6 PM - 10 PM)'),
        ('flexible', 'Flexible'),
    ]
    pt_availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES)
    preferred_days = models.CharField(max_length=200, help_text="e.g., Monday, Wednesday, Friday")
    
    # OPTIONAL FIELDS
    # Physician Information
    physician_name = models.CharField(max_length=255, null=True, blank=True)
    physician_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Current Health Care
    under_medical_care = models.BooleanField(default=False)
    medical_care_reason = models.TextField(max_length=500, null=True, blank=True)
    
    # Medications
    taking_medications = models.BooleanField(default=False)
    
    # Allergies
    allergies = models.TextField(max_length=1000, null=True, blank=True)
    
    # Basic Health Questions
    high_blood_pressure = models.BooleanField(default=False)
    bone_joint_problems = models.BooleanField(default=False)
    over_65 = models.BooleanField(default=False)
    unaccustomed_exercise = models.BooleanField(default=False)
    
    # Medical Conditions - Family History and Personal
    family_asthma = models.BooleanField(default=False)
    personal_asthma = models.TextField(max_length=500, null=True, blank=True)
    
    family_respiratory = models.BooleanField(default=False)
    personal_respiratory = models.TextField(max_length=500, null=True, blank=True)
    
    family_diabetes = models.BooleanField(default=False)
    personal_diabetes_type1 = models.TextField(max_length=200, null=True, blank=True)
    personal_diabetes_type2 = models.TextField(max_length=200, null=True, blank=True)
    diabetes_duration = models.CharField(max_length=100, null=True, blank=True)
    
    family_epilepsy = models.BooleanField(default=False)
    personal_epilepsy_petite = models.TextField(max_length=200, null=True, blank=True)
    personal_epilepsy_grand = models.TextField(max_length=200, null=True, blank=True)
    personal_epilepsy_other = models.TextField(max_length=200, null=True, blank=True)
    
    family_osteoporosis = models.BooleanField(default=False)
    personal_osteoporosis = models.TextField(max_length=500, null=True, blank=True)
    
    # Lifestyle Factors
    STRESS_LEVEL_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    occupational_stress = models.CharField(max_length=10, choices=STRESS_LEVEL_CHOICES, null=True, blank=True)
    
    ENERGY_LEVEL_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    energy_level = models.CharField(max_length=10, choices=ENERGY_LEVEL_CHOICES, null=True, blank=True)
    
    caffeine_daily = models.IntegerField(null=True, blank=True)
    alcohol_weekly = models.IntegerField(null=True, blank=True)
    colds_per_year = models.IntegerField(null=True, blank=True)
    
    anemia = models.TextField(max_length=300, null=True, blank=True)
    gastrointestinal_disorder = models.TextField(max_length=500, null=True, blank=True)
    hypoglycemia = models.TextField(max_length=300, null=True, blank=True)
    thyroid_disorder = models.TextField(max_length=300, null=True, blank=True)
    prenatal_postnatal = models.TextField(max_length=300, null=True, blank=True)
    
    # Cardiovascular
    high_bp_details = models.TextField(max_length=300, null=True, blank=True)
    hypertension_details = models.TextField(max_length=300, null=True, blank=True)
    high_cholesterol = models.TextField(max_length=500, null=True, blank=True)
    hyperlipidemia = models.TextField(max_length=500, null=True, blank=True)
    heart_disease = models.TextField(max_length=500, null=True, blank=True)
    heart_attack = models.TextField(max_length=300, null=True, blank=True)
    stroke = models.TextField(max_length=300, null=True, blank=True)
    angina = models.TextField(max_length=300, null=True, blank=True)
    gout = models.TextField(max_length=300, null=True, blank=True)
    
    # Exercise Restrictions
    exercise_restrictions = models.BooleanField(default=False)
    exercise_restrictions_details = models.TextField(max_length=1000, null=True, blank=True)
    
    chest_pain_exercise = models.BooleanField(default=False)
    chest_pain_details = models.TextField(max_length=500, null=True, blank=True)
    
    # Smoking
    SMOKING_CHOICES = [
        ('non_user', 'Non-user or former user'),
        ('cigar_pipe', 'Cigar and/or pipe'),
        ('1_15', '15 or less cigarettes per day'),
        ('16_25', '16 to 25 cigarettes per day'),
        ('26_35', '26 to 35 cigarettes per day'),
        ('35_plus', 'More than 35 cigarettes per day'),
    ]
    smoking_status = models.CharField(max_length=20, choices=SMOKING_CHOICES, null=True, blank=True)
    smoking_quit_date = models.DateField(null=True, blank=True)
    
    # Musculoskeletal Information
    head_neck_issues = models.TextField(max_length=500, null=True, blank=True)
    upper_back_issues = models.TextField(max_length=500, null=True, blank=True)
    shoulder_clavicle_issues = models.TextField(max_length=500, null=True, blank=True)
    arm_elbow_issues = models.TextField(max_length=500, null=True, blank=True)
    wrist_hand_issues = models.TextField(max_length=500, null=True, blank=True)
    lower_back_issues = models.TextField(max_length=500, null=True, blank=True)
    hip_pelvis_issues = models.TextField(max_length=500, null=True, blank=True)
    thigh_knee_issues = models.TextField(max_length=500, null=True, blank=True)
    arthritis_details = models.TextField(max_length=500, null=True, blank=True)
    hernia_details = models.TextField(max_length=300, null=True, blank=True)
    surgeries_details = models.TextField(max_length=1000, null=True, blank=True)
    other_musculoskeletal = models.TextField(max_length=500, null=True, blank=True)
    
    # Nutritional Information
    on_diet_plan = models.BooleanField(default=False)
    diet_plan_details = models.TextField(max_length=500, null=True, blank=True)
    
    taking_supplements = models.BooleanField(default=False)
    supplements_list = models.TextField(max_length=500, null=True, blank=True)
    
    weight_fluctuations = models.BooleanField(default=False)
    recent_weight_change = models.BooleanField(default=False)
    weight_change_amount = models.CharField(max_length=100, null=True, blank=True)
    weight_change_duration = models.CharField(max_length=100, null=True, blank=True)
    
    caffeine_beverages_daily = models.IntegerField(null=True, blank=True)
    nutritional_habits_description = models.TextField(max_length=1000, null=True, blank=True)
    food_allergies_issues = models.TextField(max_length=500, null=True, blank=True)
    
    # Work and Exercise Habits
    WORK_EXERCISE_CHOICES = [
        ('intense_both', 'Intense occupational and recreational exertion'),
        ('moderate_both', 'Moderate occupational and recreational exertion'),
        ('sedentary_intense', 'Sedentary occupational and intense recreational exertion'),
        ('sedentary_moderate', 'Sedentary occupational and moderate recreational exertion'),
        ('sedentary_light', 'Sedentary occupational and light recreational exertion'),
        ('no_exertion', 'Complete lack of all exertion'),
    ]
    work_exercise_habits = models.CharField(max_length=30, choices=WORK_EXERCISE_CHOICES, null=True, blank=True)
    
    STRESS_LEVEL_CHOICES = [
        ('minimal', 'Minimal'),
        ('moderate', 'Moderate'),
        ('average', 'Average'),
        ('extremely', 'Extremely'),
    ]
    work_stress_level = models.CharField(max_length=15, choices=STRESS_LEVEL_CHOICES, null=True, blank=True)
    home_stress_level = models.CharField(max_length=15, choices=STRESS_LEVEL_CHOICES, null=True, blank=True)
    
    works_over_40_hours = models.BooleanField(default=False)
    additional_comments = models.TextField(max_length=2000, null=True, blank=True)

    # Health Conditions Risky for Gym Workouts
    has_risky_heart_conditions = models.BooleanField(
        default=False, 
        help_text="Heart disease, uncontrolled high blood pressure, irregular heartbeat, history of heart attack/stroke"
    )
    risky_heart_conditions_details = models.TextField(
        max_length=1000, 
        null=True, 
        blank=True,
        help_text="Explain specific heart/cardiovascular conditions"
    )

    has_risky_health_conditions = models.BooleanField(
        default=False,
        help_text="Respiratory issues, joint problems, metabolic conditions, neurological disorders, etc."
    )
    risky_health_conditions_details = models.TextField(
        max_length=1000, 
        null=True, 
        blank=True,
        help_text="Explain specific health conditions that may be risky for gym workouts"
    ) 
        
    # Form completion
    date_completed = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Health History"
        verbose_name_plural = "Health Histories"
    
    def __str__(self):
        return f"Health History - {self.member.first_name} {self.member.last_name}"


class Medication(models.Model):
    health_history = models.ForeignKey(HealthHistory, on_delete=models.CASCADE, related_name='medications')
    medication_type = models.CharField(max_length=255)
    dosage_frequency = models.CharField(max_length=255)
    reason_for_taking = models.CharField(max_length=500)
    
    def __str__(self):
        return f"{self.medication_type} - {self.health_history.member.first_name}"


class ParqForm(models.Model):
    member = models.OneToOneField('Member', on_delete=models.CASCADE, related_name='health_history_parque')
    
    # Contact Details
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True, null=True)
    emergency_contact_mobile = models.CharField(max_length=15, blank=True, null=True)
    
    # PAR-Q Questions (YES/NO)
    heart_condition = models.BooleanField(default=False, help_text="Has your doctor ever said that you have a heart condition?")
    chest_pain_activity = models.BooleanField(default=False, help_text="Do you have chest pain brought on by physical activity?")
    chest_pain_last_month = models.BooleanField(default=False, help_text="Have you developed chest pain in the last month?")
    lose_consciousness = models.BooleanField(default=False, help_text="Do you tend to lose consciousness or fall over as a result of dizziness?")
    bone_joint_problem = models.BooleanField(default=False, help_text="Do you have a bone or joint problem that could be aggravated by physical activity?")
    medical_conditions = models.BooleanField(default=False, help_text="Do you suffer from asthma, diabetes, high blood pressure, epilepsy or a heart condition?")
    medical_conditions_specify = models.TextField(blank=True, null=True, help_text="Please specify medical conditions")
    current_treatment = models.BooleanField(default=False, help_text="Do you have any current conditions or injuries being treated by a doctor?")
    current_treatment_specify = models.TextField(blank=True, null=True, help_text="Please specify current treatment")
    other_reason = models.BooleanField(default=False, help_text="Do you know of any other reason why you should not take part in exercise?")
    other_reason_specify = models.TextField(blank=True, null=True, help_text="Please specify other reasons")
    
    # Signatures
    participant_signature = models.TextField(blank=True, null=True, help_text="Participant signature data (base64)")
    parent_guardian_signature = models.TextField(blank=True, null=True, help_text="Parent/Guardian signature data (base64)")
    tutor_signature = models.TextField(blank=True, null=True, help_text="Tutor signature data (base64)")
    
    # Dates
    form_date = models.DateField(auto_now_add=True)
    participant_signature_date = models.DateField(blank=True, null=True)
    parent_guardian_signature_date = models.DateField(blank=True, null=True)
    tutor_signature_date = models.DateField(blank=True, null=True)
    
    # Form status
    requires_doctor_consent = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Check if doctor's consent is required (if any question is answered YES)
        self.requires_doctor_consent = any([
            self.heart_condition,
            self.chest_pain_activity,
            self.chest_pain_last_month,
            self.lose_consciousness,
            self.bone_joint_problem,
            self.medical_conditions,
            self.current_treatment,
            self.other_reason
        ])
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"PAR-Q Form - {self.member.first_name}"
    
    class Meta:
        verbose_name = "PAR-Q Form"
        verbose_name_plural = "PAR-Q Forms"
