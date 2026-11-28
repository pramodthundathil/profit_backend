"""Web console pages for member app settings."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
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
