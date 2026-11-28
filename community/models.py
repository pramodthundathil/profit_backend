import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def post_media_path(instance, filename):
    return f"community/posts/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"


def avatar_path(instance, filename):
    return f"community/avatars/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"


class SocialProfile(models.Model):
    """How a member appears in the feeds. Only the display name and avatar are shown, never the real name."""

    member = models.OneToOneField('members.Member', on_delete=models.CASCADE, related_name='social_profile')
    display_name = models.CharField(max_length=40)
    bio = models.CharField(max_length=160, blank=True)
    avatar = models.ImageField(upload_to=avatar_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_member(cls, member):
        profile, _ = cls.objects.get_or_create(member=member, defaults={'display_name': member.first_name[:40] or 'Member'})
        return profile

    def __str__(self):
        return self.display_name


class Post(models.Model):
    GYM, PUBLIC = 'gym', 'public'
    VISIBILITY = ((GYM, 'My gym'), (PUBLIC, 'ProFit community'))

    KINDS = (
        ('activity', 'Activity'),
        ('workout', 'Workout'),
        ('progress', 'Progress'),
        ('meal', 'Meal'),
        ('milestone', 'Milestone'),
    )

    PUBLISHED, PENDING, HIDDEN = 'published', 'pending', 'hidden'
    STATUSES = ((PUBLISHED, 'Published'), (PENDING, 'Waiting for approval'), (HIDDEN, 'Hidden'))

    MAX_MEDIA = 4
    AUTO_HIDE_REPORTS = 3

    gym = models.ForeignKey('home.GymOffice', on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    visibility = models.CharField(max_length=10, choices=VISIBILITY, default=GYM)
    kind = models.CharField(max_length=12, choices=KINDS, default='activity')
    text = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=PUBLISHED)
    hidden_reason = models.CharField(max_length=200, blank=True)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['gym', 'status', '-id']),
            models.Index(fields=['visibility', 'status', '-id']),
            models.Index(fields=['author', '-id']),
        ]

    def __str__(self):
        return f"Post {self.pk} by {self.author_id}"


class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media')
    image = models.ImageField(upload_to=post_media_path)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    text = models.TextField()
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']


class PostReport(models.Model):
    REASONS = (
        ('spam', 'Spam'),
        ('offensive', 'Offensive or abusive'),
        ('inappropriate', 'Inappropriate photo'),
        ('other', 'Something else'),
    )

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    reason = models.CharField(max_length=20, choices=REASONS, default='other')
    details = models.CharField(max_length=300, blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'reporter')


class UserBlock(models.Model):
    """A member who no longer wants to see another member's posts and comments (both ways)."""

    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
