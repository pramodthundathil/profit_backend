from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class TrainerInstruction(models.Model):
    """A workout plan, diet plan or note a trainer sends to a member.

    `plan` holds the structured part:
      workout: {"days": [{"name": str, "exercises": [{"id", "name", "sets", "reps", "rest", "notes"}]}]}
      diet:    {"calories", "protein_g", "carbs_g", "fat_g", "meals": [{"name", "time", "items"}]}
      note:    {}
    """

    WORKOUT, DIET, NOTE = 'workout', 'diet', 'note'
    KINDS = (
        (WORKOUT, 'Workout plan'),
        (DIET, 'Diet plan'),
        (NOTE, 'Note'),
    )
    # A member follows one workout plan and one diet plan at a time.
    SINGLE_ACTIVE_KINDS = (WORKOUT, DIET)

    gym = models.ForeignKey('home.GymOffice', on_delete=models.CASCADE, related_name='trainer_instructions')
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='instructions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    kind = models.CharField(max_length=10, choices=KINDS)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    plan = models.JSONField(default=dict, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['member', 'kind', 'is_active'])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title} ({self.member})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_active and self.kind in self.SINGLE_ACTIVE_KINDS:
                TrainerInstruction.objects.filter(
                    member=self.member, kind=self.kind, is_active=True
                ).exclude(pk=self.pk).update(is_active=False)


class InstructionComment(models.Model):
    """A message on an instruction, from the member or a trainer."""

    instruction = models.ForeignKey(TrainerInstruction, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class WorkoutLog(models.Model):
    """Exercises of a workout plan a member ticked off on a day."""

    instruction = models.ForeignKey(TrainerInstruction, on_delete=models.CASCADE, related_name='workout_logs')
    log_date = models.DateField()
    completed = models.JSONField(default=list, blank=True, help_text="Exercise ids from the plan")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('instruction', 'log_date')
        ordering = ['-log_date']
