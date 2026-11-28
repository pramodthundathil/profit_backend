import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def food_photo_path(instance, filename):
    today = timezone.now()
    return f"foodlogs/{today:%Y/%m}/{uuid.uuid4().hex}.jpg"


class FoodLog(models.Model):
    """A meal a member logged."""

    MEAL_TYPES = (
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snack', 'Snack'),
        ('dinner', 'Dinner'),
        ('pre_workout', 'Pre-workout'),
        ('post_workout', 'Post-workout'),
    )
    MAX_PHOTOS = 4

    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='food_logs')
    gym = models.ForeignKey('home.GymOffice', on_delete=models.CASCADE, related_name='food_logs')
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    # The member's own calendar day and time; the server runs in UTC, which is a different day for many gyms.
    log_date = models.DateField()
    meal_time = models.TimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    calories = models.PositiveIntegerField(null=True, blank=True)
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-log_date', 'meal_time', 'created_at']
        indexes = [
            models.Index(fields=['member', 'log_date']),
            models.Index(fields=['gym', 'log_date']),
        ]

    def __str__(self):
        return f"{self.member} - {self.get_meal_type_display()} {self.log_date}"


class FoodLogPhoto(models.Model):
    food_log = models.ForeignKey(FoodLog, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to=food_photo_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class FoodLogFeedback(models.Model):
    """A trainer's review of a meal."""

    RATINGS = (
        ('great', 'Great'),
        ('ok', 'Okay'),
        ('improve', 'Needs work'),
    )

    food_log = models.ForeignKey(FoodLog, on_delete=models.CASCADE, related_name='feedback')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    rating = models.CharField(max_length=10, choices=RATINGS, blank=True)
    comment = models.TextField(blank=True)
    seen_by_member = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Feedback on {self.food_log_id}"
