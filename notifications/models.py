from django.db import models
from members.models import Member

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('EXPIRY_REMINDER', 'Expiry Reminder'),
        ('OVERDUE_ALERT', 'Overdue Alert'),
        ('PAYMENT_CONFIRMATION', 'Payment Confirmation'),
        ('DUE_REMINDER', 'Due Reminder'),
        ('SYSTEM', 'System Notification'),
    )

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['member', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.member.full_name} - {self.title} ({self.notification_type})"
