from django.db import models
from django.utils import timezone
from home.models import GymOffice, GymBranch, CustomUser
from payments.models import Payment

class FinanceTransaction(models.Model):
    TRANSACTION_TYPE = (
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    )
    
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='finance_transactions')
    branch = models.ForeignKey(
        GymBranch, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='finance_transactions',
        help_text="Branch associated with this transaction (if any)"
    )
    
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=500)
    
    # Optional fields based on custom categorizations
    category = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'Subscription', 'Salary', 'Equipment'")
    receipt_number = models.CharField(max_length=255, blank=True, null=True, help_text="Physical or digital receipt number")
    
    # Optional foreign key to actual payment record if it's tied to an auto-income from Members
    payment = models.ForeignKey(
        Payment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='finance_records'
    )
    
    # Staff/Admin member who recorded the transaction
    recorded_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='recorded_transactions'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['gym', 'transaction_type']),
            models.Index(fields=['branch', 'transaction_type']),
            models.Index(fields=['date']),
        ]
        
    def __str__(self):
        return f"{self.transaction_type} - ₹{self.amount} - {self.description[:30]}"
