from django.db import models
from django.utils import timezone
from datetime import timedelta

class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_valid(self):
        # OTP is valid for 10 minutes
        return timezone.now() < self.created_at + timedelta(minutes=10) and not self.is_verified

    def __str__(self):
        return f"{self.email} - {self.otp}"
