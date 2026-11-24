from datetime import timedelta
from django.utils import timezone
from home.models import CustomUser, GymOffice
from home.plans import available_plans
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

# Create your tests here.


class PlanTests(TestCase):
    def setUp(self):
        self.gym = GymOffice.objects.create(name="G", address="x", email="g@example.com")

    def prices(self):
        return [p['price'] for p in available_plans(self.gym)]

    def test_first_year_only_plan(self):
        self.assertEqual(self.prices(), [10600])
        self.gym.subscription_started_at = timezone.now() - timedelta(days=200)
        self.assertEqual(self.prices(), [10600])

    def test_renewal_plans_after_one_year(self):
        self.gym.subscription_started_at = timezone.now() - timedelta(days=367)
        self.assertEqual(self.prices(), [900, 2500, 6900])



class MobileSubscriptionGateTests(TestCase):
    STATUS = '/auth/users/subscription/status/'
    GATED = [
        '/auth/users/dashboard/stats/',
        '/v2/members/api/members/list/',
        '/v2/members/api/subscriptions/list/',
        '/v2/payments/api/list/',
    ]

    def setUp(self):
        self.gym = GymOffice.objects.create(name="G", address="x", email="g@example.com")
        self.user = self.make_user('gym_admin')

    def make_user(self, role):
        return CustomUser.objects.create_user(
            email=f"{role}@example.com", password="x", role=role, gym=self.gym,
            phone_number=f"98765432{len(role):02d}")

    def get(self, path, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return self.client.get(path, HTTP_AUTHORIZATION=f'Bearer {token}')

    def expire(self):
        self.gym.trial_ends_at = timezone.now() - timedelta(days=1)
        self.gym.save()

    def test_active_gym_has_access(self):
        for path in self.GATED:
            self.assertEqual(self.get(path).status_code, 200, path)
        self.assertTrue(self.get(self.STATUS).json()['can_access'])

    def test_expired_gym_is_blocked(self):
        self.expire()
        for path in self.GATED:
            res = self.get(path)
            self.assertEqual(res.status_code, 403, path)
            self.assertEqual(res.json()['code'], 'LICENSE_EXPIRED')

    def test_expired_gym_can_still_read_status_and_profile(self):
        self.expire()
        data = self.get(self.STATUS).json()
        self.assertFalse(data['can_access'])
        self.assertEqual(data['status_text'], 'Expired')
        self.assertEqual([p['price'] for p in data['plans']], [10600])
        self.assertEqual(self.get('/auth/users/users/me/').status_code, 200)

    def test_renewal_restores_access(self):
        self.expire()
        self.gym.extend_subscription(months=1)
        self.assertEqual(self.get(self.GATED[0]).status_code, 200)

    def test_members_are_not_gated(self):
        self.expire()
        member = self.make_user('member')
        self.assertEqual(self.get('/auth/users/users/', member).status_code, 200)
