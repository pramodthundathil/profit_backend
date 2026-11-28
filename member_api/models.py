from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailOTP(models.Model):
    MAX_ATTEMPTS = 5
    VALID_FOR = timedelta(minutes=10)

    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    def is_valid(self):
        return (
            not self.is_verified
            and self.attempts < self.MAX_ATTEMPTS
            and timezone.now() < self.created_at + self.VALID_FOR
        )

    def __str__(self):
        return f"{self.email} ({self.created_at:%Y-%m-%d %H:%M})"


class MemberAppSettings(models.Model):
    """Which member app features a gym has switched on."""

    FEATURE_FIELDS = (
        'member_login_enabled',
        'community_feed_enabled',
        'public_feed_enabled',
        'food_log_enabled',
        'trainer_instructions_enabled',
        'require_post_approval',
    )

    gym = models.OneToOneField(
        'home.GymOffice', on_delete=models.CASCADE, related_name='member_app_settings'
    )
    # Members still need login enabled one by one; this switch turns the app off for the whole gym.
    member_login_enabled = models.BooleanField(default=True)
    community_feed_enabled = models.BooleanField(
        default=True, help_text="Members can post to and read their gym's feed"
    )
    public_feed_enabled = models.BooleanField(
        default=False, help_text="Members can post to and read the feed shared by all ProFit gyms"
    )
    food_log_enabled = models.BooleanField(default=True)
    trainer_instructions_enabled = models.BooleanField(default=True)
    require_post_approval = models.BooleanField(
        default=False, help_text="A trainer or admin approves posts before others see them"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        verbose_name = "Member app settings"
        verbose_name_plural = "Member app settings"

    @classmethod
    def for_gym(cls, gym):
        obj, _ = cls.objects.get_or_create(gym=gym)
        return obj

    def features(self):
        return {name: getattr(self, name) for name in self.FEATURE_FIELDS}

    def __str__(self):
        return f"Member app settings - {self.gym}"


class MemberAppAccount(models.Model):
    """App login state for a member whose login a gym enabled."""

    member = models.OneToOneField(
        'members.Member', on_delete=models.CASCADE, related_name='app_account'
    )
    must_change_password = models.BooleanField(default=True)
    credentials_sent_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    enabled_at = models.DateTimeField(default=timezone.now)
    enabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    def __str__(self):
        return f"App account - {self.member}"
