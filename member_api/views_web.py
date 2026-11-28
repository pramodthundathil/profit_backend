"""Web console pages for member app settings."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from members.models import Member
from .models import MemberAppSettings
from . import services

FEATURES = [
    ('member_login_enabled', 'Member app login',
     "Members whose login you enable can sign in to the ProFit member app. Turning this off signs every member out of the app."),
    ('community_feed_enabled', 'Gym feed',
     "Members can post their activity and see posts from members of this gym."),
    ('public_feed_enabled', 'ProFit community feed',
     "Members can also post to and see the feed shared by all gyms on ProFit. Only their display name is shown there."),
    ('food_log_enabled', 'Food log',
     "Members can log meals with photos, and trainers can review them."),
    ('trainer_instructions_enabled', 'Trainer instructions',
     "Trainers can send workout plans, diet plans and notes to their members."),
    ('require_post_approval', 'Approve posts first',
     "A trainer or admin must approve posts before other members can see them."),
]


def _eligible(user):
    members = Member.objects.filter(gym=user.gym)
    if user.role == 'branch_admin' and user.branch_id:
        members = members.filter(branch_id=user.branch_id)
    return services.eligible_for_bulk_enable(members)


@login_required
def member_app_settings(request):
    user = request.user
    if user.role not in ('gym_admin', 'branch_admin') or not user.gym:
        messages.error(request, "Only administrators can manage member app settings.")
        return redirect('user-dashboard')

    settings_obj = MemberAppSettings.for_gym(user.gym)
    can_edit = user.role == 'gym_admin'

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, "Only the gym owner can change member app settings.")
            return redirect('member-app-settings')
        for name, _, _ in FEATURES:
            setattr(settings_obj, name, request.POST.get(name) == 'on')
        settings_obj.updated_by = user
        settings_obj.save()
        messages.success(request, "Member app settings saved.")
        return redirect('member-app-settings')

    context = {
        'title': 'Member App',
        'features': [
            {'name': name, 'label': label, 'help': help_text, 'value': getattr(settings_obj, name)}
            for name, label, help_text in FEATURES
        ],
        'can_edit': can_edit,
        'login_enabled': settings_obj.member_login_enabled,
        'eligible_count': _eligible(user).count(),
        'enabled_count': Member.objects.filter(gym=user.gym, user__isnull=False, user__is_active=True).count(),
    }
    return render(request, 'user/member_app_settings.html', context)


@login_required
@require_POST
def member_app_bulk_enable(request):
    user = request.user
    if user.role not in ('gym_admin', 'branch_admin') or not user.gym:
        messages.error(request, "Only administrators can enable logins in bulk.")
        return redirect('user-dashboard')
    if not MemberAppSettings.for_gym(user.gym).member_login_enabled:
        messages.error(request, "Turn on member app login first.")
        return redirect('member-app-settings')

    result = services.bulk_enable(_eligible(user), user)
    if result['enabled']:
        messages.success(request, f"Login enabled for {result['enabled']} members. Their login emails are being sent.")
    for failure in result['failed'][:5]:
        messages.warning(request, f"{failure['name']} ({failure['member_id']}): {failure['error']}")
    if len(result['failed']) > 5:
        messages.warning(request, f"{len(result['failed']) - 5} more members could not be enabled.")
    if not result['enabled'] and not result['failed']:
        messages.info(request, "No members need login enabled.")
    return redirect('member-app-settings')


# --- Coaching: food log review and trainer instructions ---------------------

import json
from datetime import timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from foodlog.models import FoodLog, FoodLogFeedback
from training.models import InstructionComment, TrainerInstruction
from .coaching import COACH_ROLES, coached_members, day_summary
from .coaching_serializers import InstructionSerializer


def _coach_member(request, pk):
    """The member if the signed-in user may coach them; otherwise 404."""
    if request.user.role not in COACH_ROLES or not request.user.gym:
        raise Http404
    return get_object_or_404(coached_members(request.user), pk=pk)


def _first_error(detail):
    if isinstance(detail, dict):
        for value in detail.values():
            return _first_error(value)
    if isinstance(detail, list) and detail:
        return _first_error(detail[0])
    return str(detail)


@login_required
def member_coaching(request, pk):
    member = _coach_member(request, pk)
    features = MemberAppSettings.for_gym(request.user.gym)
    tab = request.GET.get('tab') or ('food' if features.food_log_enabled else 'plans')

    try:
        end = timezone.datetime.fromisoformat(request.GET['date']).date()
    except (KeyError, ValueError):
        end = timezone.localdate()
    start = end - timedelta(days=6)

    logs = (
        FoodLog.objects.filter(member=member, log_date__range=(start, end))
        .prefetch_related('photos', 'feedback__author')
        .order_by('-log_date', 'meal_time', 'created_at')
    )
    days = []
    for offset in range(7):
        day = end - timedelta(days=offset)
        days.append({'date': day, 'summary': day_summary(member, day), 'meals': [l for l in logs if l.log_date == day]})

    instructions = (
        TrainerInstruction.objects.filter(member=member)
        .select_related('author').prefetch_related('comments__author')
    )
    context = {
        'title': f'Coaching: {member.full_name}',
        'member': member,
        'features': features,
        'tab': tab,
        'days': days,
        'end': end,
        'prev_date': (end - timedelta(days=7)).isoformat(),
        'next_date': (end + timedelta(days=7)).isoformat() if end < timezone.localdate() else None,
        'active_instructions': [i for i in instructions if i.is_active],
        'past_instructions': [i for i in instructions if not i.is_active],
        'ratings': FoodLogFeedback.RATINGS,
    }
    return render(request, 'user/coaching/member_coaching.html', context)


@login_required
@require_POST
def coaching_feedback(request, pk, log_id):
    member = _coach_member(request, pk)
    if not MemberAppSettings.for_gym(request.user.gym).food_log_enabled:
        messages.error(request, "Food log is turned off for this gym.")
        return redirect('member-coaching', pk=pk)
    log = get_object_or_404(FoodLog, pk=log_id, member=member)
    rating = request.POST.get('rating', '')
    comment = request.POST.get('comment', '').strip()
    if rating not in dict(FoodLogFeedback.RATINGS):
        rating = ''
    if not rating and not comment:
        messages.error(request, "Choose a rating or write a comment.")
    else:
        FoodLogFeedback.objects.create(food_log=log, author=request.user, rating=rating, comment=comment[:2000])
        messages.success(request, "Feedback sent.")
    return redirect(f"{reverse('member-coaching', args=[pk])}?tab=food&date={request.POST.get('date', '')}#meal-{log.pk}")


@login_required
@require_POST
def coaching_comment(request, pk, instruction_id):
    member = _coach_member(request, pk)
    instruction = get_object_or_404(TrainerInstruction, pk=instruction_id, member=member)
    body = request.POST.get('body', '').strip()
    if body:
        InstructionComment.objects.create(instruction=instruction, author=request.user, body=body[:2000])
    return redirect(f"{reverse('member-coaching', args=[pk])}?tab=plans#instruction-{instruction.pk}")


@login_required
@require_POST
def coaching_instruction_action(request, pk, instruction_id):
    member = _coach_member(request, pk)
    instruction = get_object_or_404(TrainerInstruction, pk=instruction_id, member=member)
    action = request.POST.get('action')
    if action == 'delete':
        instruction.delete()
        messages.success(request, "Instruction deleted.")
    elif action in ('activate', 'deactivate'):
        instruction.is_active = action == 'activate'
        instruction.save()
        messages.success(request, "Instruction updated.")
    return redirect(f"{reverse('member-coaching', args=[pk])}?tab=plans")


@login_required
def coaching_instruction_form(request, pk, instruction_id=None):
    member = _coach_member(request, pk)
    if not MemberAppSettings.for_gym(request.user.gym).trainer_instructions_enabled:
        messages.error(request, "Trainer instructions are turned off for this gym.")
        return redirect('member-coaching', pk=pk)
    instruction = get_object_or_404(TrainerInstruction, pk=instruction_id, member=member) if instruction_id else None
    kind = instruction.kind if instruction else request.GET.get('kind', TrainerInstruction.WORKOUT)
    if kind not in dict(TrainerInstruction.KINDS):
        kind = TrainerInstruction.WORKOUT

    error = None
    values = {
        'title': instruction.title if instruction else '',
        'body': instruction.body if instruction else '',
        'start_date': (instruction.start_date if instruction else timezone.localdate()).isoformat(),
        'end_date': instruction.end_date.isoformat() if instruction and instruction.end_date else '',
        'plan': instruction.plan if instruction else {},
    }

    if request.method == 'POST':
        try:
            plan = json.loads(request.POST.get('plan') or '{}')
        except ValueError:
            plan = {}
        data = {
            'kind': kind,
            'title': request.POST.get('title', '').strip(),
            'body': request.POST.get('body', '').strip(),
            'plan': plan,
            'start_date': request.POST.get('start_date') or timezone.localdate().isoformat(),
            'end_date': request.POST.get('end_date') or None,
        }
        if not instruction:
            data['is_active'] = True
        serializer = InstructionSerializer(instruction, data=data, partial=bool(instruction))
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            error = _first_error(exc.detail)
            values.update({k: data[k] or '' for k in ('title', 'body', 'start_date', 'end_date')}, plan=plan)
        else:
            if instruction:
                serializer.save()
            else:
                serializer.save(member=member, gym=member.gym, author=request.user)
            messages.success(request, "Instruction saved. The member can see it in the app.")
            return redirect(f"{reverse('member-coaching', args=[pk])}?tab=plans")

    context = {
        'title': f"{'Edit' if instruction else 'New'} {dict(TrainerInstruction.KINDS)[kind].lower()}",
        'member': member,
        'instruction': instruction,
        'kind': kind,
        'values': values,
        'error': error,
    }
    return render(request, 'user/coaching/instruction_form.html', context)


# --- Community moderation ------------------------------------------------------

from community.moderation import filtered as moderation_filtered, FILTERS as MODERATION_FILTERS
from community.models import Post as CommunityPost, PostReport


@login_required
def community_moderation(request):
    if request.user.role not in COACH_ROLES or not request.user.gym:
        messages.error(request, "Only trainers and admins can moderate the community.")
        return redirect('user-dashboard')

    if request.method == 'POST':
        post = get_object_or_404(CommunityPost, pk=request.POST.get('post_id'), gym=request.user.gym)
        action = request.POST.get('action')
        if action in ('approve', 'restore'):
            post.status, post.hidden_reason = CommunityPost.PUBLISHED, ''
            post.save(update_fields=['status', 'hidden_reason', 'updated_at'])
            PostReport.objects.filter(post=post).update(resolved=True)
            messages.success(request, "Post published.")
        elif action == 'hide':
            post.status, post.hidden_reason = CommunityPost.HIDDEN, 'Hidden by the gym team'
            post.save(update_fields=['status', 'hidden_reason', 'updated_at'])
            PostReport.objects.filter(post=post).update(resolved=True)
            messages.success(request, "Post hidden.")
        elif action == 'delete':
            for media in post.media.all():
                media.delete()
            post.delete()
            messages.success(request, "Post deleted.")
        return redirect(f"{reverse('community-moderation')}?filter={request.POST.get('filter', 'pending')}")

    current = request.GET.get('filter', 'pending')
    if current not in MODERATION_FILTERS:
        current = 'pending'
    posts = moderation_filtered(request.user, current).select_related('author__member_profile').prefetch_related('reports')[:60]
    context = {
        'title': 'Community',
        'filter': current,
        'counts': {key: moderation_filtered(request.user, key).count() for key in ('pending', 'reported', 'hidden')},
        'posts': posts,
        'features': MemberAppSettings.for_gym(request.user.gym),
    }
    return render(request, 'user/coaching/community_moderation.html', context)
