from django.db.models.signals import post_save
from django.dispatch import receiver
from payments.models import Payment
from finance.models import FinanceTransaction
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """
    When a Payment is completed, log an Income transaction.
    """
    if instance.status == 'Completed':
        # Check if already recorded to avoid duplicates when payment is updated
        finance_exists = FinanceTransaction.objects.filter(payment=instance).exists()
        
        if not finance_exists:
            try:
                # Find the corresponding member's gym and branch
                gym = instance.member.gym
                branch = instance.member.branch
                
                FinanceTransaction.objects.create(
                    gym=gym,
                    branch=branch,
                    transaction_type='Income',
                    amount=instance.amount,
                    date=instance.payment_date,
                    description=f"Subscription Payment - {instance.member.full_name}",
                    category="Subscription",
                    receipt_number=instance.receipt_number,
                    payment=instance,
                    # No specific recorded_by unless we deduce from collected_by (which is string, not FK)
                    recorded_by=None
                )
                logger.info(f"FinanceTransaction created for Payment {instance.receipt_number}")
            except Exception as e:
                logger.error(f"Error creating FinanceTransaction for Payment {instance.id}: {str(e)}")
        else:
            # If the payment fields have updated, we could optionally update the finance record.
            # But normally completed payments shouldn't change amount/date.
            pass
