from django.db.models.signals import post_save
from django.dispatch import receiver
from payments.models import Payment
from .models import Notification
from utils.emails import send_notification_email

@receiver(post_save, sender=Payment)
def payment_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'Completed':
        # Create notification for member
        title = "Payment Received"
        message = f"Payment of {instance.amount} received from {instance.member.full_name} (ID: {instance.member.member_id}). Receipt: {instance.receipt_number}."
        
        Notification.objects.create(
            member=instance.member,
            title=title,
            message=message,
            notification_type='PAYMENT_CONFIRMATION'
        )
        
        # Send email
        send_notification_email(instance.member, title, message)
