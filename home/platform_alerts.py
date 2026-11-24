"""Gym-level alerts for the super admin: plan expiry and recharges.

Alerts are derived from live data, so an expiry alert disappears by itself
once the gym is renewed, disabled or deleted.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .models import GymOffice, LicenseKey, PaymentTransaction, SubscriptionHistory

PLAN_WARNING_DAYS = 30
TRIAL_WARNING_DAYS = 7
RECHARGE_HISTORY_DAYS = 90

PAYMENT_STYLES = {
    'completed': ('Recharge received', 'success', 'bi-check-circle'),
    'pending': ('Recharge pending', 'warning', 'bi-hourglass-split'),
    'failed': ('Recharge failed', 'danger', 'bi-x-circle'),
    'refunded': ('Recharge refunded', 'neutral', 'bi-arrow-counterclockwise'),
}


def _alert(gym, category, level, icon, title, message, **extra):
    return {
        'gym': gym, 'category': category, 'level': level, 'icon': icon,
        'title': title, 'message': message, 'date': None,
        'needs_action': False,
        'url': reverse('gym-office-detail', args=[gym.pk]), **extra,
    }


def plan_state(gym):
    """Return (kind, end_date) for the entitlement that keeps the gym open longest."""
    ends = []
    if gym.license_key and gym.license_key.valid_until:
        ends.append((gym.license_key.valid_until, 'License'))
    if gym.subscription_valid_until:
        ends.append((gym.subscription_valid_until, 'Subscription'))
    if gym.trial_ends_at:
        ends.append((gym.trial_ends_at.date(), 'Trial'))
    if not ends:
        return 'Plan', None
    end, kind = max(ends)
    return kind, end


def expiry_alerts(gyms):
    today = timezone.now().date()
    alerts = []
    for gym in gyms:
        if not gym.is_active:
            continue
        kind, end = plan_state(gym)
        days = (end - today).days if end else None
        if not gym.can_access_service():
            message = f"Access stopped. {kind} ended on {end:%d %b %Y}." if end else "No active plan."
            alerts.append(_alert(gym, 'expiry', 'danger', 'bi-exclamation-octagon',
                                 f"{kind} expired", message, date=end,
                                 days=days if days is not None else -9999, needs_action=True))
            continue
        limit = TRIAL_WARNING_DAYS if kind == 'Trial' else PLAN_WARNING_DAYS
        if days is not None and days <= limit:
            when = 'today' if days <= 0 else 'tomorrow' if days == 1 else f'in {days} days'
            alerts.append(_alert(gym, 'expiry', 'danger' if days <= 3 else 'warning', 'bi-clock-history',
                                 f"{kind} expires {when}", f"Renew before {end:%d %b %Y} to keep access.",
                                 date=end, days=days, needs_action=True))
    # Upcoming first (soonest at the top), then the most recently expired.
    alerts.sort(key=lambda a: (a['days'] < 0, abs(a['days'])))
    return alerts


def recharge_alerts():
    since = timezone.now() - timedelta(days=RECHARGE_HISTORY_DAYS)
    alerts = []
    live = {'is_deleted': False, 'gym__is_deleted': False, 'created_at__gte': since}

    for pay in PaymentTransaction.objects.filter(**live).select_related('gym'):
        title, level, icon = PAYMENT_STYLES.get(pay.status, PAYMENT_STYLES['pending'])
        alerts.append(_alert(pay.gym, 'recharge', level, icon, title,
                             f"₹{pay.amount} for {pay.plan_name}.",
                             date=pay.created_at,
                             needs_action=pay.status in ('pending', 'failed')))

    # Renewals made without a payment; paid ones are already listed above.
    for sub in SubscriptionHistory.objects.filter(payment_transaction=None, **live).select_related('gym'):
        alerts.append(_alert(sub.gym, 'recharge', 'success', 'bi-arrow-repeat', 'Subscription renewed',
                             f"{sub.plan_name}, valid until {sub.expires_at:%d %b %Y}.",
                             date=sub.created_at))

    licenses = LicenseKey.objects.filter(
        is_deleted=False, gym_office__is_deleted=False, created_at__gte=since,
    ).select_related('gym_office')
    for key in licenses:
        valid = f"Valid until {key.valid_until:%d %b %Y}." if key.valid_until else "No expiry date set."
        alerts.append(_alert(key.gym_office, 'recharge', 'success', 'bi-key', 'License issued',
                             valid, date=key.created_at))

    alerts.sort(key=lambda a: a['date'], reverse=True)
    return alerts


def get_platform_alerts(request):
    """Build alerts once per request (shared by views and the context processor)."""
    if not hasattr(request, '_platform_alerts'):
        gyms = GymOffice.objects.filter(is_deleted=False).select_related('license_key')
        expiry, recharge = expiry_alerts(gyms), recharge_alerts()
        everything = expiry + recharge
        request._platform_alerts = {
            'expiry': expiry,
            'recharge': recharge,
            'all': everything,
            'attention_count': sum(a['needs_action'] for a in everything),
        }
    return request._platform_alerts
