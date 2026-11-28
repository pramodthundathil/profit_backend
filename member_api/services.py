"""Member app login: enabling accounts, credentials and the email that carries them."""
import logging
import re
import secrets
import threading
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import close_old_connections, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from home.models import CustomUser
from .models import MemberAppAccount, MemberAppSettings

logger = logging.getLogger(__name__)

# No 0/O, 1/l/I so the password can be typed from an email without guessing.
PASSWORD_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
MIN_PASSWORD_LENGTH = 8


class MemberLoginError(Exception):
    """A member's login cannot be changed; the message is safe to show staff."""


@dataclass
class Credentials:
    member: object
    password: str


def generate_temp_password(length=10):
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def _clean_phone(number):
    """CustomUser validates phone numbers strictly; members are entered more loosely."""
    number = (number or '').strip()
    digits = re.sub(r'\D', '', number)
    if not 9 <= len(digits) <= 15:
        raise MemberLoginError("The member's mobile number is not valid. Fix it before enabling login.")
    return ('+' if number.startswith('+') else '') + digits


def get_account(member):
    """The member's app account, created for logins enabled before accounts existed."""
    account, _ = MemberAppAccount.objects.get_or_create(
        member=member, defaults={'must_change_password': False}
    )
    return account


def login_status(member):
    user = member.user
    if user is None:
        state = 'not_enabled'
    elif not user.is_active:
        state = 'disabled'
    else:
        state = 'enabled'
    account = MemberAppAccount.objects.filter(member=member).first() if user else None
    return {
        'state': state,
        'email': member.email,
        'username': user.email if user else None,
        'member_id': member.member_id,
        'must_change_password': bool(account and account.must_change_password),
        'credentials_sent_at': account.credentials_sent_at if account else None,
        'last_login': user.last_login if user else None,
        'can_enable': bool(member.email),
    }


def _ensure_gym_allows_login(member):
    if not MemberAppSettings.for_gym(member.gym).member_login_enabled:
        raise MemberLoginError("Member app login is turned off for this gym. Turn it on in Member App settings.")


def _issue_password(member, user, actor):
    password = generate_temp_password()
    user.set_password(password)
    user.is_active = True
    user.save()
    MemberAppAccount.objects.update_or_create(
        member=member,
        defaults={
            'must_change_password': True,
            'enabled_by': actor,
            'enabled_at': timezone.now(),
        },
    )
    return Credentials(member=member, password=password)


@transaction.atomic
def enable_login(member, actor=None):
    """Create or reactivate the member's login and return a new temporary password."""
    if not member.email:
        raise MemberLoginError("Add an email address to this member before enabling login.")
    _ensure_gym_allows_login(member)

    user = member.user
    if user is not None:
        if user.is_active:
            raise MemberLoginError("App login is already enabled. Use 'Resend credentials' to send a new password.")
        if user.email.lower() != member.email.lower():
            if CustomUser.objects.filter(email__iexact=member.email).exclude(pk=user.pk).exists():
                raise MemberLoginError("This email address is already used by another ProFit account.")
            user.email = CustomUser.objects.normalize_email(member.email)
        return _issue_password(member, user, actor)

    existing = CustomUser.objects.filter(email__iexact=member.email).first()
    if existing is not None:
        # Only an unlinked member account of the same gym (left by the old OTP login) can be reused.
        reusable = (
            existing.role == 'member'
            and existing.gym_id == member.gym_id
            and not hasattr(existing, 'member_profile')
        )
        if not reusable:
            raise MemberLoginError(
                "This email address is already used by another ProFit account. "
                "Use a different email for this member."
            )
        user = existing
    else:
        user = CustomUser(
            email=CustomUser.objects.normalize_email(member.email),
            role='member',
            gym=member.gym,
            branch=member.branch if member.branch and member.branch.gym_id == member.gym_id else None,
            phone_number=_clean_phone(member.mobile_number),
            username=member.member_id,
        )
        user.set_unusable_password()
        user.save()

    member.user = user
    member.save(update_fields=['user'])
    return _issue_password(member, user, actor)


@transaction.atomic
def reset_credentials(member, actor=None):
    """Give an enabled member a new temporary password."""
    user = member.user
    if user is None or not user.is_active:
        raise MemberLoginError("App login is not enabled for this member.")
    if not member.email:
        raise MemberLoginError("Add an email address to this member first.")
    _ensure_gym_allows_login(member)
    if user.email.lower() != member.email.lower():
        if CustomUser.objects.filter(email__iexact=member.email).exclude(pk=user.pk).exists():
            raise MemberLoginError("This email address is already used by another ProFit account.")
        user.email = CustomUser.objects.normalize_email(member.email)
    _revoke_sessions(user)
    return _issue_password(member, user, actor)


def _revoke_sessions(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


@transaction.atomic
def disable_login(member):
    """Block the member's login but keep the account, so posts and logs survive re-enabling."""
    user = member.user
    if user is None or not user.is_active:
        raise MemberLoginError("App login is not enabled for this member.")
    user.is_active = False
    user.save()
    _revoke_sessions(user)


def _credentials_message(credentials, connection=None):
    member = credentials.member
    context = {
        'first_name': member.first_name,
        'gym_name': member.gym.name,
        'member_id': member.member_id,
        'username': member.user.email,
        'password': credentials.password,
        'app_url': getattr(settings, 'MEMBER_APP_DOWNLOAD_URL', ''),
    }
    message = EmailMultiAlternatives(
        subject=f"Your {member.gym.name} app login",
        body=render_to_string('member_api/emails/credentials.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[member.user.email],
        connection=connection,
    )
    message.attach_alternative(render_to_string('member_api/emails/credentials.html', context), 'text/html')
    return message


def send_credentials(credentials, connection=None):
    """Email the member their login. Returns False instead of raising if sending fails."""
    try:
        _credentials_message(credentials, connection).send(fail_silently=False)
    except Exception:
        logger.exception("Could not send member app credentials to member %s", credentials.member.pk)
        return False
    MemberAppAccount.objects.filter(member=credentials.member).update(credentials_sent_at=timezone.now())
    return True


def send_credentials_in_background(credentials_list):
    """Send many credential emails over one connection without holding up the request."""
    if not credentials_list:
        return

    def run():
        try:
            with get_connection() as connection:
                for credentials in credentials_list:
                    send_credentials(credentials, connection)
        except Exception:
            logger.exception("Bulk member credential emails failed")
        finally:
            close_old_connections()

    # The thread reads the new accounts, so wait until they are committed.
    transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())


def eligible_for_bulk_enable(members):
    """Members of a queryset who have an email and no login yet."""
    return members.filter(user__isnull=True).exclude(email__isnull=True).exclude(email='')


def bulk_enable(members, actor=None):
    """Enable login for each eligible member and email them in the background."""
    enabled, failed = [], []
    for member in eligible_for_bulk_enable(members).select_related('gym', 'branch'):
        try:
            enabled.append(enable_login(member, actor))
        except MemberLoginError as error:
            failed.append({'member_id': member.member_id, 'name': member.full_name, 'error': str(error)})
    send_credentials_in_background(enabled)
    return {'enabled': len(enabled), 'failed': failed}


def validate_new_password(user, password):
    """Return an error message, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.isdigit():
        return "Password cannot be only numbers."
    if user.check_password(password):
        return "Choose a password different from your current one."
    return None
