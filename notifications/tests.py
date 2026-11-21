from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.test import TestCase, SimpleTestCase, Client
from django.utils import timezone
from django.urls import reverse

from home.models import GymOffice, CustomUser
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
