from django.db import models
from django.utils import timezone

from members.models import Member, Subscription
from home.models import GymBranch, GymOffice


# Create your models here.

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
            gym_code = self.member.gym.code
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
        
        super().save(*args, **kwargs)
        
        # Update subscription payment status
        if self.status == 'Completed':
            self.subscription.update_payment_status()
    
    @property
    def is_full_payment(self):
        """Check if this payment completes the subscription"""
        return self.subscription.is_fully_paid
    
    def __str__(self):
        installment_info = f" (Installment {self.installment_number})" if self.is_installment else ""
        return f"{self.receipt_number} - {self.member.full_name} - ₹{self.amount}{installment_info}"


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
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'Percentage' else '₹'}"


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