from django.db import models
from home.models import GymOffice, GymBranch

# Configuration models (gym-specific)
class Batch_DB(models.Model):
    """Batches are now gym/branch specific"""
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='batches')
    batch_name = models.CharField(
        max_length=255,
        choices=(("Morning","Morning"), ("Evening","Evening"), ("Night","Night"))
    )
    batch_status = models.BooleanField(default=True)
    batch_time = models.TimeField()
    
    class Meta:
        unique_together = ['gym', 'batch_name', 'batch_time']
        verbose_name = "Batch"
        verbose_name_plural = "Batches"
    
    def __str__(self):
        return f"{self.gym.name}: {self.batch_name} {self.batch_time}"


class TypeSubscription(models.Model):
    """Subscription types per gym (e.g., 'Zumba', 'CrossFit', 'Personal Training')"""
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='subscription_types')
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['gym', 'name']
    
    def __str__(self):
        return f"{self.gym.name} - {self.name}"


class SubscriptionPeriod(models.Model):
    """Period configurations per gym"""
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='subscription_periods')
    period = models.PositiveIntegerField()
    class Meta:
        unique_together = ['gym', 'period']
    
    def __str__(self):
        return f"{self.gym.name}: {self.period} days"

