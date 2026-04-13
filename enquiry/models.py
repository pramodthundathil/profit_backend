from django.db import models
from home.models import GymOffice

class EnquiryData(models.Model):
    gym = models.ForeignKey(GymOffice, on_delete=models.CASCADE, related_name='enquiries')
    date_created = models.DateField(auto_now_add=True)
    date_updated = models.DateField(auto_now=True)
    name = models.CharField(max_length=250)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    number_of_followup = models.IntegerField(default=0)

    last_follow_up_date = models.DateField(null=True, blank=True)
    next_follow_up_date = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('in_progress', 'In Progress'),
        ('not_required', 'Not Required'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    conversion = models.BooleanField(default=False)
    converted_member = models.ForeignKey(
        'members.Member', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='converted_from_enquiries'
    )

    class Meta:
        verbose_name_plural = "Enquiry Data"

    def __str__(self):
        return f"Enquiry - {self.name} ({self.gym.name})"


class EnquiryStatus(models.Model):
    enquiry = models.ForeignKey(EnquiryData, on_delete=models.CASCADE, related_name='statuses')
    date_of_status = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('in_progress', 'In Progress'),
        ('not_required', 'Not Required'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    
    LEAD_STATUS_CHOICES = [
        ('rnr', 'RNR'),
        ('callback', 'Callback'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('converted', 'Converted'),
        ('follow_up', 'Follow Up'),
        ('closed', 'Closed'),
    ]
    call_status = models.CharField(max_length=30, choices=LEAD_STATUS_CHOICES, default='rnr')

    class Meta:
        verbose_name_plural = "Enquiry Statuses"

    def __str__(self):
        return f"Status for {self.enquiry.name} on {self.date_of_status.date()}"
