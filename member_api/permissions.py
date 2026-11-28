from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from members.models import Member
from .models import MemberAppSettings

MEMBER_APP_DISABLED = 'MEMBER_APP_DISABLED'
PASSWORD_CHANGE_REQUIRED = 'PASSWORD_CHANGE_REQUIRED'

STAFF_ROLES = ('gym_admin', 'branch_admin', 'staff')


def member_app_disabled():
    return PermissionDenied({
        'code': MEMBER_APP_DISABLED,
        'detail': 'Your gym has turned off the member app. Contact your gym for help.',
    })


class IsAppMember(BasePermission):
    """An active member of a gym that allows app login. Sets request.member.

    Until the member replaces their temporary password, only views with
    `allow_pending_password = True` are reachable.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.role == 'member'):
            return False
        member = Member.objects.select_related('gym', 'branch').filter(user=user).first()
        if member is None:
            return False
        if not MemberAppSettings.for_gym(member.gym).member_login_enabled:
            raise member_app_disabled()

        account = getattr(member, 'app_account', None)
        if account and account.must_change_password and not getattr(view, 'allow_pending_password', False):
            raise PermissionDenied({
                'code': PASSWORD_CHANGE_REQUIRED,
                'detail': 'Set a new password to continue.',
            })
        request.member = member
        return True


class IsGymStaff(BasePermission):
    """Gym admins, branch managers and front-desk staff."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in STAFF_ROLES and user.gym_id)


class IsGymAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == 'gym_admin' and user.gym_id)


def can_manage_member(user, member):
    """Staff tied to a branch can only manage that branch's members."""
    if member.gym_id != user.gym_id:
        return False
    if user.role == 'gym_admin':
        return True
    if user.role in ('branch_admin', 'staff') and user.branch_id:
        return member.branch_id == user.branch_id
    return user.role == 'staff'
