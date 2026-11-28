from rest_framework import serializers

from member_api.coaching import compress_photo
from .models import Post, PostComment, PostReport, SocialProfile


def author_card(user, request):
    """What others see of an author: a display name and avatar only."""
    member = getattr(user, 'member_profile', None)
    me = bool(request and request.user.id == user.id)
    if member is not None:
        profile = getattr(member, 'social_profile', None) or SocialProfile.for_member(member)
        avatar = profile.avatar.url if profile.avatar else None
        return {
            'profile_id': profile.pk,
            'display_name': profile.display_name,
            'avatar': request.build_absolute_uri(avatar) if avatar and request else avatar,
            'is_me': me,
            'is_staff': False,
        }
    return {'profile_id': None, 'display_name': 'Gym team', 'avatar': None, 'is_me': me, 'is_staff': True}


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    liked_by_me = serializers.BooleanField(read_only=True, default=False)
    visibility_display = serializers.CharField(source='get_visibility_display', read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'visibility', 'visibility_display', 'kind', 'kind_display', 'text', 'media',
            'like_count', 'comment_count', 'liked_by_me', 'status', 'created_at',
        ]
        read_only_fields = ['like_count', 'comment_count', 'created_at']

    def get_author(self, obj):
        return author_card(obj.author, self.context.get('request'))

    def get_media(self, obj):
        request = self.context.get('request')
        return [{'id': m.id, 'image': request.build_absolute_uri(m.image.url) if request else m.image.url} for m in obj.media.all()]

    def get_status(self, obj):
        # Only the author learns that a post is waiting or hidden.
        request = self.context.get('request')
        if request and obj.author_id == request.user.id:
            return obj.status
        return Post.PUBLISHED

    def validate_text(self, value):
        return value.strip()[:2000]

    def validate(self, data):
        request = self.context['request']
        uploads = request.FILES.getlist('photos')
        if len(uploads) > Post.MAX_MEDIA:
            raise serializers.ValidationError({'photos': f'A post can have at most {Post.MAX_MEDIA} photos.'})
        if not data.get('text') and not uploads:
            raise serializers.ValidationError('Write something or add a photo.')
        data['_photos'] = [compress_photo(upload) for upload in uploads]
        return data


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = PostComment
        fields = ['id', 'author', 'text', 'can_delete', 'created_at']
        read_only_fields = ['created_at']

    def get_author(self, obj):
        return author_card(obj.author, self.context.get('request'))

    def get_can_delete(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.id in (obj.author_id, obj.post.author_id))

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Write a comment.')
        return value[:1000]


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReport
        fields = ['reason', 'details']


class SocialProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = SocialProfile
        fields = ['id', 'display_name', 'bio', 'avatar', 'post_count']

    def get_avatar(self, obj):
        request = self.context.get('request')
        if not obj.avatar:
            return None
        return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url

    def get_post_count(self, obj):
        return self.context.get('post_count')


class SocialProfileUpdateSerializer(serializers.ModelSerializer):
    remove_avatar = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = SocialProfile
        fields = ['display_name', 'bio', 'remove_avatar']

    def validate_display_name(self, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError('Use at least 2 characters.')
        return value[:40]

    def validate_bio(self, value):
        return value.strip()[:160]
