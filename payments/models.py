from django.db import models
from django.utils import timezone

from members.models import Member, Subscription
from home.models import GymBranch, GymOffice


# Create your models here.

# ============================================================================
# OFFER MODEL
# ============================================================================

class GymOffer(models.Model):
    """Gym-wide offers for specific periods"""
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='offers')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Percentage discount to apply (e.g., 10 for 10%)"
    )
    
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # Optional: restricts offer to specific members
    specific_members = models.ManyToManyField(
        Member, 
        blank=True, 
        related_name='eligible_offers',
        help_text="If empty, applies to all members of the gym"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def is_currently_valid(self, member=None):
        """Check if offer is valid today and applicable to member"""
        today = timezone.now().date()
        if not self.is_active:
            return False
        if not (self.start_date <= today <= self.end_date):
            return False
        if self.specific_members.exists() and member:
            if not self.specific_members.filter(id=member.id).exists():
                return False
        return True

    @classmethod
    def get_active_offer(cls, gym, member=None):
        """
        Priority Scoping Logic:
        1. Look for active offers specific to the member.
        2. If none, look for active global offers for the gym.
        Returns the most recent single offer or None.
        """
        today = timezone.now().date()
        base_qs = cls.objects.filter(
            gym=gym,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today
        ).order_by('-created_at')

        if member:
            # 1. Try specific offers
            specific_offer = base_qs.filter(specific_members=member).first()
            if specific_offer:
                return specific_offer

        # 2. Try global offers (specific_members is empty)
        # Note: In Django, if a M2M is empty, .filter(specific_members=None) works 
        # but usually it's better to check .annotate(count=Count('specific_members')).filter(count=0)
        # However, for simplicity and since we only care about if anyone is IN it:
        global_offer = base_qs.filter(specific_members__isnull=True).first()
        return global_offer

    def __str__(self):
        return f"{self.name} ({self.discount_percentage}%)"


# ============================================================================
# PAYMENT MODEL
# ============================================================================

class Payment(models.Model):
    """Payment transactions"""
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    
    installment = models.ForeignKey(
        'members.SubscriptionInstallment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Offer Tracking
    offer = models.ForeignKey(
        GymOffer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount discounted via an offer"
    )
    
    # Payment Details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=50,
        choices=(
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("Bank Transfer", "Bank Transfer"),
            ("UPI", "UPI"),
            ("Cheque", "Cheque"),
            ("Online", "Online"),
            ("Tabby", "Tabby")
        )
    )
    
    # Installment Info
    is_installment = models.BooleanField(default=False)
    installment_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Which installment is this (1, 2, 3...)"
    )
    
    # Dates
    payment_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=(
            ("Pending", "Pending"),
            ("Completed", "Completed"),
            ("Failed", "Failed"),
            ("Refunded", "Refunded")
        ),
        default="Completed"
    )
    
    # Transaction Details
    transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Bank/Payment gateway transaction ID"
    )
    receipt_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False
    )
    
    # Additional Info
    notes = models.TextField(blank=True, null=True)
    collected_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Staff member who collected payment"
    )
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['member', 'payment_date']),
            models.Index(fields=['payment_date']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Generate unique receipt number
            gym_code = (self.member.gym.name[:3].upper() if self.member.gym.name else "GYM")
            today = timezone.now().strftime('%Y%m%d')
            
            last_payment = Payment.objects.filter(
                receipt_number__startswith=f"RCP-{gym_code}-{today}"
            ).order_by('-id').first()
            
            if last_payment:
                try:
                    last_seq = int(last_payment.receipt_number.split('-')[-1])
                    new_seq = last_seq + 1
                except:
                    new_seq = 1
            else:
                new_seq = 1
            
            self.receipt_number = f"RCP-{gym_code}-{today}-{new_seq:04d}"
        
        # Auto-sync installment info
        if self.installment:
            self.is_installment = True
            if not self.installment_number:
                self.installment_number = self.installment.installment_number

        super().save(*args, **kwargs)
        
        # Update installment status if this payment is linked to one
        if self.installment:
            self.installment.update_payment_status()
            
        # Update subscription payment status
        if self.status == 'Completed':
            self.subscription.update_payment_status()
    
    @property
    def is_full_payment(self):
        """Check if this payment completes the subscription"""
        return self.subscription.is_fully_paid
    
    def __str__(self):
        installment_info = f" (Installment {self.installment_number})" if self.is_installment else ""
        symbol = self.member.gym.currency_symbol if self.member.gym else '₹'
        return f"{self.receipt_number} - {self.member.full_name} - {symbol}{self.amount}{installment_info}"


# ============================================================================
# DISCOUNT COUPON (Optional - for promotions)
# ============================================================================

class DiscountCoupon(models.Model):
    """Promotional discount coupons (optional)"""
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='discount_coupons')
    
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    discount_type = models.CharField(
        max_length=20,
        choices=(
            ("Percentage", "Percentage"),
            ("Fixed", "Fixed Amount")
        )
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Validity
    valid_from = models.DateField()
    valid_until = models.DateField()
    
    # Usage Limits
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited"
    )
    uses_count = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-valid_from']
    
    def is_valid(self):
        """Check if coupon is valid"""
        today = timezone.now().date()
        
        if not self.is_active:
            return False, "Coupon is inactive"
        
        if today < self.valid_from:
            return False, "Coupon not yet valid"
        
        if today > self.valid_until:
            return False, "Coupon has expired"
        
        if self.max_uses and self.uses_count >= self.max_uses:
            return False, "Coupon usage limit reached"
        
        return True, "Valid"
    
    def calculate_discount(self, amount):
        """Calculate discount amount"""
        if self.discount_type == "Percentage":
            return (amount * self.discount_value) / 100
        else:
            return min(self.discount_value, amount)
    
    def apply_coupon(self):
        """Increment usage count"""
        self.uses_count += 1
        self.save()
    
    def __str__(self):
        symbol = self.gym.currency_symbol if self.gym else '₹'
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'Percentage' else symbol}"


class CouponUsage(models.Model):
    """Track which members used which coupons"""
    coupon = models.ForeignKey(DiscountCoupon, on_delete=models.CASCADE, related_name='usages')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='coupon_usages')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='coupon_used')
    
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
    
    def __str__(self):
        return f"{self.member.full_name} used {self.coupon.code}"