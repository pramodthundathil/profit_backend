from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.test import TestCase, SimpleTestCase, Client
from django.utils import timezone
from django.urls import reverse

from home.models import GymBranch, GymOffice, CustomUser, PaymentTransaction
from members.models import Member, Subscription
from notifications.models import Notification
from utils.whatsapp import format_phone_number, send_whatsapp_template, send_member_expiry_whatsapp


class WhatsAppUnitTests(SimpleTestCase):
    def test_format_phone_number(self):
        self.assertEqual(format_phone_number("9876543210"), "919876543210")
        self.assertEqual(format_phone_number("+91 98765-43210"), "919876543210")
        self.assertEqual(format_phone_number("919876543210"), "919876543210")
        self.assertEqual(format_phone_number(""), "")

    @patch('utils.whatsapp.requests.post')
    def test_send_whatsapp_template_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"messages": [{"id": "wamid.123"}]}'
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_post.return_value = mock_response

        success, msg, data = send_whatsapp_template(
            recipient="9876543210",
            customer_name="Rahul",
            expiry_date="26/11/2026",
            gym_name="PowerFitness Gym"
        )

        self.assertTrue(success)
        self.assertTrue(mock_post.called)
        
        # Verify payload parameters
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs['json']
        
        self.assertEqual(payload['messaging_product'], 'whatsapp')
        self.assertEqual(payload['to'], '919876543210')
        self.assertEqual(payload['type'], 'template')
        
        components = payload['template']['components']
        body_component = next(c for c in components if c['type'] == 'body')
        params = body_component['parameters']
        
        # Verify {{1}} customer name, {{2}} expiry date, {{3}} gym name
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0]['text'], 'Rahul')
        self.assertEqual(params[1]['text'], '26/11/2026')
        self.assertEqual(params[2]['text'], 'PowerFitness Gym')


class WhatsAppExpiryTests(TestCase):
    def setUp(self):
        self.gym = GymOffice.objects.create(
            name="PowerFitness Gym",
            address="123 Test St",
            email="testgym@example.com",
            phone="+919876543210"
        )
        self.user = CustomUser.objects.create_user(
            email="admin@powerfitness.com",
            phone_number="+919876543210",
            password="testpassword123",
            role="gym_admin",
            gym=self.gym
        )
        self.member = Member.objects.create(
            gym=self.gym,
            first_name="Rahul",
            last_name="Sharma",
            mobile_number="9876543210",
            gender="Male"
        )
        self.client = Client()
        self.client.force_login(self.user)

        body_component = next(c for c in components if c['type'] == 'body')
        params = body_component['parameters']
        
        # Verify {{1}} customer name, {{2}} expiry date, {{3}} gym name
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0]['text'], 'Rahul')
        self.assertEqual(params[1]['text'], '26/11/2026')
        self.assertEqual(params[2]['text'], 'PowerFitness Gym')

    @patch('utils.whatsapp.requests.post')
    def test_send_member_expiry_whatsapp(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"messages": [{"id": "wamid.123"}]}'
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_post.return_value = mock_response

        today = timezone.now().date()
        expiry_date = today + timedelta(days=5)
        
        sub = Subscription.objects.create(
            member=self.member,
            duration=30,
            duration_unit="Days",
            start_date=today - timedelta(days=25),
            end_date=expiry_date,
            base_amount=1000,
            final_amount=1000,
            amount_paid=1000,
            status='Active'
        )

        success, msg = send_member_expiry_whatsapp(self.member, subscription=sub)
        self.assertTrue(success)

        # Check that Notification record was created
        notif = Notification.objects.filter(member=self.member, notification_type='EXPIRY_REMINDER').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "WhatsApp Expiry Reminder")
        self.assertIn("PowerFitness Gym", notif.message)

    @patch('utils.whatsapp.requests.post')
    def test_manual_send_view(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"messages": [{"id": "wamid.123"}]}'
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_post.return_value = mock_response

        today = timezone.now().date()
        sub = Subscription.objects.create(
            member=self.member,
            duration=30,
            duration_unit="Days",
            start_date=today - timedelta(days=25),
            end_date=today + timedelta(days=5),
            base_amount=1000,
            final_amount=1000,
            amount_paid=1000,
            status='Active'
        )

        # Post to manual send view
        url = reverse('member-send-expiry-whatsapp', kwargs={'pk': self.member.pk})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify message was logged
        notif = Notification.objects.filter(member=self.member, notification_type='EXPIRY_REMINDER').first()
        self.assertIsNotNone(notif)

    @patch('utils.whatsapp.requests.post')
    def test_management_command_5_days_check(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"messages": [{"id": "wamid.123"}]}'
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_post.return_value = mock_response

        today = timezone.now().date()
        expiry_date = today + timedelta(days=5)

        # Create active subscription expiring exactly in 5 days
        sub = Subscription.objects.create(
            member=self.member,
            duration=30,
            duration_unit="Days",
            start_date=today - timedelta(days=25),
            end_date=expiry_date,
            base_amount=1000,
            final_amount=1000,
            amount_paid=1000,
            status='Active'
        )

        from django.core.management import call_command
        call_command('check_notifications')

        # Check in-app notification for 5-day expiry
        notif_5d = Notification.objects.filter(
            member=self.member,
            title="Subscription Expiring Soon (5 Days)"
        ).first()
        self.assertIsNotNone(notif_5d)

        # Check WhatsApp notification
        notif_wa = Notification.objects.filter(
            member=self.member,
            title="WhatsApp Expiry Reminder"
        ).first()
        self.assertIsNotNone(notif_wa)


class SuperAdminAlertTests(TestCase):
    def setUp(self):
        self.gym = GymOffice.objects.create(name="Gym A", address="x", email="a@example.com", phone="9876543210")
        self.other = GymOffice.objects.create(name="Gym B", address="x", email="b@example.com", phone="9876543211")
        self.admin = CustomUser.objects.create_user(
            email="root@example.com", password="x", role="admin", phone_number="9876543212")
        self.owner = CustomUser.objects.create_user(
            email="own@example.com", password="x", role="gym_admin", gym=self.gym, phone_number="9876543213")
        branch = GymBranch.objects.create(name="B", address="x", email="br@example.com", gym=self.other)
        member = Member.objects.create(
            gym=self.other, branch=branch, first_name="Other", last_name="Member",
            mobile_number="9876543214", email="m@example.com")
        self.notif = Notification.objects.create(
            member=member, title="Member receipt", message="x", notification_type="PAYMENT_CONFIRMATION")

    def test_admin_sees_gym_alerts_not_member_notifications(self):
        now = timezone.now()
        GymOffice.objects.filter(pk=self.gym.pk).update(trial_ends_at=now - timedelta(days=2))
        PaymentTransaction.objects.create(gym=self.other, amount=100, plan_name="1 Month", status="completed")
        self.client.force_login(self.admin)
        html = self.client.get(reverse('notification-list')).content.decode()
        self.assertIn("Trial expired", html)
        self.assertIn("Recharge received", html)
        self.assertNotIn("Member receipt", html)
        self.client.post(reverse('notification-clear-all'))
        self.assertTrue(Notification.objects.filter(pk=self.notif.pk).exists())

    def test_renewed_or_disabled_gym_has_no_expiry_alert(self):
        GymOffice.objects.filter(pk=self.gym.pk).update(
            trial_ends_at=timezone.now() - timedelta(days=2),
            subscription_valid_until=timezone.now().date() + timedelta(days=200))
        GymOffice.objects.filter(pk=self.other.pk).update(
            trial_ends_at=timezone.now() - timedelta(days=2), is_active=False)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notification-list') + '?type=expiry')
        self.assertEqual(response.context['alerts'], [])

    def test_gym_admin_cannot_touch_other_gyms_notifications(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('notification-list')), "Member receipt")
        self.assertEqual(self.client.post(reverse('notification-delete', args=[self.notif.pk])).status_code, 404)
        self.client.post(reverse('notification-mark-all-read'))
        self.client.post(reverse('notification-clear-all'))
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)
