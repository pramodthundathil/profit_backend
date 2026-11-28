from django.db import transaction
from rest_framework import serializers

from foodlog.models import FoodLog, FoodLogFeedback, FoodLogPhoto
from members.models import Member
from training.models import InstructionComment, TrainerInstruction
from .coaching import author_name, clean_plan, compress_photo


class FoodLogPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodLogPhoto
        fields = ['id', 'image']


class FoodLogFeedbackSerializer(serializers.ModelSerializer):
    rating_display = serializers.CharField(source='get_rating_display', read_only=True)
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = FoodLogFeedback
        fields = ['id', 'rating', 'rating_display', 'comment', 'author_name', 'seen_by_member', 'created_at']
        read_only_fields = ['seen_by_member', 'created_at']

    def get_author_name(self, obj):
        return author_name(obj.author)

    def validate(self, data):
        if not data.get('rating') and not (data.get('comment') or '').strip():
            raise serializers.ValidationError('Choose a rating or write a comment.')
        return data


class FoodLogSerializer(serializers.ModelSerializer):
    """Members write meals with up to 4 photos sent as multipart `photos` files."""

    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)
    photos = FoodLogPhotoSerializer(many=True, read_only=True)
    feedback = FoodLogFeedbackSerializer(many=True, read_only=True)
    remove_photo_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = FoodLog
        fields = [
            'id', 'meal_type', 'meal_type_display', 'log_date', 'meal_time', 'description',
            'calories', 'protein_g', 'carbs_g', 'fat_g', 'photos', 'feedback', 'remove_photo_ids',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'calories': {'max_value': 10000},
            'protein_g': {'min_value': 0, 'max_value': 1000},
            'carbs_g': {'min_value': 0, 'max_value': 2000},
            'fat_g': {'min_value': 0, 'max_value': 1000},
        }

    def _uploads(self):
        request = self.context.get('request')
        return request.FILES.getlist('photos') if request else []

    def validate(self, data):
        uploads = self._uploads()
        existing = self.instance.photos.count() if self.instance else 0
        removing = len(set(data.get('remove_photo_ids') or []))
        if existing - removing + len(uploads) > FoodLog.MAX_PHOTOS:
            raise serializers.ValidationError({'photos': f'A meal can have at most {FoodLog.MAX_PHOTOS} photos.'})
        description = data.get('description', self.instance.description if self.instance else '')
        if not (description or '').strip() and existing - removing + len(uploads) == 0:
            raise serializers.ValidationError('Add a photo or describe what you ate.')
        # Compress here so a bad file fails validation before anything is saved.
        data['_photos'] = [compress_photo(upload) for upload in uploads]
        return data

    @transaction.atomic
    def _save_photos(self, log, photos, remove_ids):
        if remove_ids:
            for photo in log.photos.filter(pk__in=remove_ids):
                photo.delete()
        for content in photos:
            photo = FoodLogPhoto(food_log=log)
            photo.image.save(content.name, content, save=True)

    def create(self, validated_data):
        photos = validated_data.pop('_photos', [])
        validated_data.pop('remove_photo_ids', None)
        log = super().create(validated_data)
        self._save_photos(log, photos, None)
        return log

    def update(self, instance, validated_data):
        photos = validated_data.pop('_photos', [])
        remove_ids = validated_data.pop('remove_photo_ids', None)
        log = super().update(instance, validated_data)
        self._save_photos(log, photos, remove_ids)
        return log


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    from_member = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = InstructionComment
        fields = ['id', 'body', 'author_name', 'from_member', 'is_mine', 'created_at']
        read_only_fields = ['created_at']

    def get_author_name(self, obj):
        if obj.author and obj.author.role == 'member':
            member = getattr(obj.author, 'member_profile', None)
            return member.first_name if member else 'Member'
        return author_name(obj.author)

    def get_from_member(self, obj):
        return bool(obj.author and obj.author.role == 'member')

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return bool(request and obj.author_id == request.user.id)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Write a message.')
        return value[:2000]


class InstructionSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    author_name = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = TrainerInstruction
        fields = [
            'id', 'kind', 'kind_display', 'title', 'body', 'plan', 'start_date', 'end_date',
            'is_active', 'author_name', 'comment_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_author_name(self, obj):
        return author_name(obj.author)

    def validate(self, data):
        kind = data.get('kind', self.instance.kind if self.instance else None)
        if self.instance and 'kind' in data and data['kind'] != self.instance.kind:
            raise serializers.ValidationError({'kind': 'The type of an instruction cannot be changed.'})
        if 'plan' in data or not self.instance:
            data['plan'] = clean_plan(kind, data.get('plan') or {})
        if kind == TrainerInstruction.NOTE and not (data.get('body') or (self.instance and self.instance.body)):
            raise serializers.ValidationError({'body': 'Write the note.'})
        start = data.get('start_date', self.instance.start_date if self.instance else None)
        end = data.get('end_date', self.instance.end_date if self.instance else None)
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'The end date must be after the start date.'})
        return data


class InstructionDetailSerializer(InstructionSerializer):
    comments = CommentSerializer(many=True, read_only=True)

    class Meta(InstructionSerializer.Meta):
        fields = InstructionSerializer.Meta.fields + ['comments']


class CoachedMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    last_food_log_date = serializers.DateField(read_only=True)
    unreviewed_meals = serializers.IntegerField(read_only=True)
    has_workout_plan = serializers.BooleanField(read_only=True)
    has_diet_plan = serializers.BooleanField(read_only=True)
    app_login = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'id', 'member_id', 'full_name', 'photo', 'branch_name', 'membership_status',
            'last_food_log_date', 'unreviewed_meals', 'has_workout_plan', 'has_diet_plan', 'app_login',
        ]

    def get_app_login(self, obj):
        return bool(obj.user_id and obj.user.is_active)
