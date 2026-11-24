from datetime import timedelta
from django.utils import timezone
from home.models import GymOffice
from home.plans import available_plans
from django.test import TestCase

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
