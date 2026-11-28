"""Shared rules for food logs and trainer instructions: who may coach whom, feature switches, photos, plans."""
import uuid
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from foodlog.models import FoodLog
from members.models import Member
from training.models import TrainerInstruction
from .models import MemberAppSettings

FEATURE_DISABLED = 'FEATURE_DISABLED'
COACH_ROLES = ('trainer', 'gym_admin', 'branch_admin')

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
PHOTO_MAX_SIDE = 1600


# --- Who may coach whom -------------------------------------------------------

def coached_members(user):
    """Members this trainer or admin can see food logs for and send instructions to."""
    members = Member.objects.filter(gym=user.gym).select_related('branch', 'gym')
    if user.role == 'trainer':
        return members.filter(assigned_trainer=user)
    if user.role == 'branch_admin' and user.branch_id:
        return members.filter(branch_id=user.branch_id)
    if user.role == 'gym_admin':
        return members
    return members.none()


def can_coach(user, member):
    return coached_members(user).filter(pk=member.pk).exists()


class IsCoach(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in COACH_ROLES and user.gym_id)


def feature_required(feature, label):
    """A permission that rejects requests when the gym has switched `feature` off.

    Use after IsAppMember (member requests) or IsCoach (staff requests).
    """

    class FeatureEnabled(BasePermission):
        def has_permission(self, request, view):
            member = getattr(request, 'member', None)
            gym = member.gym if member else getattr(request.user, 'gym', None)
            if gym is None or not getattr(MemberAppSettings.for_gym(gym), feature):
                raise PermissionDenied({
                    'code': FEATURE_DISABLED,
                    'detail': f'{label} is turned off for this gym.',
                })
            return True

    return FeatureEnabled


FoodLogEnabled = feature_required('food_log_enabled', 'Food log')
InstructionsEnabled = feature_required('trainer_instructions_enabled', 'Trainer instructions')


def author_name(user):
    if user is None:
        return 'Former staff'
    return user.username or user.email.split('@')[0]


def parse_date(value, default_today=True):
    if not value:
        if default_today:
            return timezone.localdate()
        raise serializers.ValidationError({'date': 'Send a date as YYYY-MM-DD.'})
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        raise serializers.ValidationError({'date': 'Send a date as YYYY-MM-DD.'})


# --- Photos -------------------------------------------------------------------

def compress_photo(upload):
    """Re-encode an uploaded photo as a JPEG no larger than PHOTO_MAX_SIDE on its long edge.

    Re-encoding also strips EXIF data such as the location the photo was taken at.
    """
    if upload.size > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError({'photos': 'Each photo must be smaller than 15 MB.'})
    try:
        Image.open(upload).verify()
        upload.seek(0)
        image = ImageOps.exif_transpose(Image.open(upload))
        image = image.convert('RGB')
        image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise serializers.ValidationError({'photos': 'Upload photos as JPEG or PNG.'})
    buffer = BytesIO()
    image.save(buffer, 'JPEG', quality=82, optimize=True)
    return ContentFile(buffer.getvalue(), name='photo.jpg')


# --- Plans --------------------------------------------------------------------

def _text(value, limit):
    return str(value or '').strip()[:limit]


def _number(value, field, maximum, decimal=False):
    if value in (None, ''):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise serializers.ValidationError({'plan': f'{field} must be a number.'})
    if number < 0 or number > maximum:
        raise serializers.ValidationError({'plan': f'{field} must be between 0 and {maximum}.'})
    return float(round(number, 1)) if decimal else int(number)


def clean_workout_plan(plan):
    days = plan.get('days') if isinstance(plan, dict) else None
    if not isinstance(days, list) or not days:
        raise serializers.ValidationError({'plan': 'Add at least one day to the workout.'})
    if len(days) > 14:
        raise serializers.ValidationError({'plan': 'A workout can have at most 14 days.'})

    cleaned = []
    for index, day in enumerate(days, start=1):
        day = day if isinstance(day, dict) else {}
        name = _text(day.get('name'), 100) or f'Day {index}'
        exercises = []
        for exercise in (day.get('exercises') or [])[:40]:
            if not isinstance(exercise, dict) or not _text(exercise.get('name'), 120):
                continue
            exercises.append({
                # Ticks in WorkoutLog refer to this id, so it survives edits to the plan.
                'id': _text(exercise.get('id'), 16) or uuid.uuid4().hex[:8],
                'name': _text(exercise.get('name'), 120),
                'sets': _number(exercise.get('sets'), 'Sets', 50),
                'reps': _text(exercise.get('reps'), 30),
                'rest': _text(exercise.get('rest'), 30),
                'notes': _text(exercise.get('notes'), 300),
            })
        if not exercises:
            raise serializers.ValidationError({'plan': f'Add at least one exercise to {name}.'})
        cleaned.append({'name': name, 'exercises': exercises})
    return {'days': cleaned}


def clean_diet_plan(plan):
    plan = plan if isinstance(plan, dict) else {}
    meals = []
    for meal in (plan.get('meals') or [])[:12]:
        if not isinstance(meal, dict) or not (_text(meal.get('name'), 60) or _text(meal.get('items'), 500)):
            continue
        meals.append({
            'name': _text(meal.get('name'), 60) or 'Meal',
            'time': _text(meal.get('time'), 20),
            'items': _text(meal.get('items'), 500),
        })
    cleaned = {
        'calories': _number(plan.get('calories'), 'Calories', 10000),
        'protein_g': _number(plan.get('protein_g'), 'Protein', 1000, decimal=True),
        'carbs_g': _number(plan.get('carbs_g'), 'Carbs', 2000, decimal=True),
        'fat_g': _number(plan.get('fat_g'), 'Fat', 1000, decimal=True),
        'meals': meals,
    }
    if cleaned['calories'] is None and not meals:
        raise serializers.ValidationError({'plan': 'Add a calorie target or at least one meal.'})
    return cleaned


def clean_plan(kind, plan):
    if kind == TrainerInstruction.WORKOUT:
        return clean_workout_plan(plan)
    if kind == TrainerInstruction.DIET:
        return clean_diet_plan(plan)
    return {}


def exercise_ids(instruction):
    return {e['id'] for day in instruction.plan.get('days', []) for e in day.get('exercises', [])}


# --- Food summary -------------------------------------------------------------

def day_summary(member, day):
    """What a member ate on a day, against their active diet plan's targets."""
    logs = FoodLog.objects.filter(member=member, log_date=day)
    totals = logs.aggregate(
        calories=Sum('calories'), protein_g=Sum('protein_g'), carbs_g=Sum('carbs_g'), fat_g=Sum('fat_g'),
    )
    diet = TrainerInstruction.objects.filter(member=member, kind=TrainerInstruction.DIET, is_active=True).first()
    targets = None
    if diet:
        targets = {key: diet.plan.get(key) for key in ('calories', 'protein_g', 'carbs_g', 'fat_g')}
    return {
        'date': day.isoformat(),
        'meals': logs.count(),
        'totals': {key: float(value) if value is not None else 0 for key, value in totals.items()},
        'targets': targets,
        'diet_plan_id': diet.pk if diet else None,
    }
