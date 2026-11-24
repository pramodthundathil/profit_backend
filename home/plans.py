"""Platform plans a gym can buy. Prices are in INR and exclude GST."""
from dateutil.relativedelta import relativedelta
from django.utils import timezone

FIRST_YEAR_PLANS = [
    {'id': 'plan_first_year', 'name': 'First Year Plan', 'price': 10600, 'duration': '12 Months',
     'months': 12, 'extra': '+ GST (setup charges included)'},
]

# Available only once the gym has completed its first year.
RENEWAL_PLANS = [
    {'id': 'plan_monthly', 'name': 'Monthly Plan', 'price': 900, 'duration': '1 Month',
     'months': 1, 'extra': '+ GST'},
    {'id': 'plan_quarterly', 'name': 'Quarterly Plan', 'price': 2500, 'duration': '3 Months',
     'months': 3, 'extra': '+ GST'},
    {'id': 'plan_annual', 'name': 'Yearly Plan', 'price': 6900, 'duration': '12 Months',
     'months': 12, 'extra': '+ GST'},
]


def has_completed_first_year(gym):
    """True when the gym's first subscription or license began at least a year ago.

    The free trial does not count towards the first year.
    """
    starts = [gym.subscription_started_at]
    starts.append(gym.subscription_history.filter(is_deleted=False)
                  .order_by('started_at').values_list('started_at', flat=True).first())
    if gym.license_key:
        starts.append(gym.license_key.created_at)
    starts = [s for s in starts if s]
    if not starts:
        return False
    return min(starts).date() + relativedelta(years=1) <= timezone.now().date()


def _for_display(plans):
    return [{**plan, 'price_display': f"{plan['price']:,}"} for plan in plans]


def available_plans(gym):
    """Plans the gym can buy now."""
    return _for_display(RENEWAL_PLANS if has_completed_first_year(gym) else FIRST_YEAR_PLANS)


def upcoming_plans(gym):
    """Plans shown for information only, until the first year is complete."""
    return [] if has_completed_first_year(gym) else _for_display(RENEWAL_PLANS)
