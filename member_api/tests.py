import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from home.models import CustomUser, GymOffice
from members.models import Member
from .models import EmailOTP, MemberAppAccount, MemberAppSettings
from . import services

API = '/v5/member-api/'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MemberLoginTests(TestCase):
    def setUp(self):
        cache.clear()  # reset rate limits between tests
        self.gym = GymOffice.objects.create(name="Iron Gym", address="x", email="gym@example.com")
        self.admin = CustomUser.objects.create_user(
            email="owner@example.com", phone_number="+919876543210", password="ownerpass123",
            role="gym_admin", gym=self.gym,
        )
        self.member = Member.objects.create(
            gym=self.gym, first_name="Asha", last_name="K", mobile_number="98765 43210",
            gender="Female", email="asha@example.com",
        )
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.admin)
        self.client = APIClient()

    def enable(self):
        response = self.staff_client.post(f'{API}admin/members/{self.member.pk}/login/enable/')
        self.assertEqual(response.status_code, 200, response.data)
        return re.search(r'Temporary password: (\S+)', mail.outbox[-1].body).group(1)

    def login(self, identifier, password):
        return self.client.post(f'{API}auth/login/', {'identifier': identifier, 'password': password}, format='json')

    def test_enable_emails_credentials_and_forces_password_change(self):
        password = self.enable()
        self.member.refresh_from_db()
        self.assertEqual(mail.outbox[0].to, ['asha@example.com'])
        self.assertIn(self.member.member_id, mail.outbox[0].body)
        self.assertEqual(self.member.user.phone_number, '9876543210')

        response = self.login(self.member.member_id, password)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['must_change_password'])
        token = response.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Everything but config and change-password waits for the new password
        self.assertEqual(self.client.get(f'{API}profile/').data['code'], 'PASSWORD_CHANGE_REQUIRED')
        self.assertTrue(self.client.get(f'{API}config/').data['must_change_password'])

        response = self.client.post(f'{API}auth/change-password/',
                                    {'password': 'newpass123', 'confirm_password': 'newpass123'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")
        self.assertEqual(self.client.get(f'{API}profile/').status_code, 200)

        self.client.credentials()
        self.assertEqual(self.login('ASHA@example.com', 'newpass123').status_code, 200)
        self.assertEqual(self.login('asha@example.com', password).status_code, 401)

    def test_later_password_change_needs_current_password(self):
        password = self.enable()
        account = self.member.app_account
        account.must_change_password = False
        account.save()
        token = self.login('asha@example.com', password).data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        body = {'password': 'newpass123', 'confirm_password': 'newpass123'}
        self.assertEqual(self.client.post(f'{API}auth/change-password/', body, format='json').status_code, 400)
        body['current_password'] = password
        self.assertEqual(self.client.post(f'{API}auth/change-password/', body, format='json').status_code, 200)

    def test_gym_switch_blocks_login_and_existing_sessions(self):
        password = self.enable()
        token = self.login('asha@example.com', password).data['tokens']['access']
        MemberAppSettings.objects.filter(gym=self.gym).update(member_login_enabled=False)

        self.assertEqual(self.login('asha@example.com', password).data['code'], 'MEMBER_APP_DISABLED')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get(f'{API}config/').data['code'], 'MEMBER_APP_DISABLED')

        response = self.staff_client.post(f'{API}admin/members/{self.member.pk}/login/resend/')
        self.assertEqual(response.status_code, 400)

    def test_disable_keeps_account_and_reenable_sends_new_password(self):
        old_password = self.enable()
        user_id = Member.objects.get(pk=self.member.pk).user_id
        self.assertEqual(self.staff_client.post(f'{API}admin/members/{self.member.pk}/login/disable/').status_code, 200)
        self.assertEqual(self.login('asha@example.com', old_password).status_code, 403)

        new_password = self.enable()
        self.assertEqual(Member.objects.get(pk=self.member.pk).user_id, user_id)
        self.assertEqual(self.login('asha@example.com', new_password).status_code, 200)

    def test_will_not_take_over_another_account_with_same_email(self):
        CustomUser.objects.create_user(email="asha@example.com", phone_number="+919876543211",
                                       password="x" * 10, role="staff", gym=self.gym)
        response = self.staff_client.post(f'{API}admin/members/{self.member.pk}/login/enable/')
        self.assertEqual(response.status_code, 400)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.user)

    def test_other_gym_staff_cannot_manage_member(self):
        other_gym = GymOffice.objects.create(name="Other", address="x", email="other@example.com")
        outsider = CustomUser.objects.create_user(email="o@example.com", phone_number="+919876543212",
                                                  password="x" * 10, role="gym_admin", gym=other_gym)
        client = APIClient()
        client.force_authenticate(outsider)
        self.assertEqual(client.post(f'{API}admin/members/{self.member.pk}/login/enable/').status_code, 404)

    def test_otp_reset_flow(self):
        self.enable()
        response = self.client.post(f'{API}auth/send-otp/', {'email': 'asha@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        code = EmailOTP.objects.get(email='asha@example.com').otp

        wrong = '000000' if code != '000000' else '111111'
        self.assertEqual(self.client.post(f'{API}auth/verify-otp/', {'email': 'asha@example.com', 'otp': wrong}, format='json').status_code, 400)
        response = self.client.post(f'{API}auth/verify-otp/', {'email': 'asha@example.com', 'otp': code}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['must_change_password'])

    def test_otp_is_not_sent_for_unknown_or_unenabled_email(self):
        for email in ('nobody@example.com', 'asha@example.com'):  # asha has no login yet
            response = self.client.post(f'{API}auth/send-otp/', {'email': email}, format='json')
            self.assertEqual(response.status_code, 200)
        self.assertFalse(EmailOTP.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_otp_locks_after_too_many_wrong_codes(self):
        self.enable()
        self.client.post(f'{API}auth/send-otp/', {'email': 'asha@example.com'}, format='json')
        otp = EmailOTP.objects.get(email='asha@example.com')
        otp.attempts = EmailOTP.MAX_ATTEMPTS
        otp.save()
        response = self.client.post(f'{API}auth/verify-otp/', {'email': 'asha@example.com', 'otp': otp.otp}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_bulk_enable_skips_members_without_email(self):
        Member.objects.create(gym=self.gym, first_name="No", last_name="Email", mobile_number="9876543219", gender="Male")
        class InlineThread:  # run the email sender in this thread so the test database is shared
            def __init__(self, target, **kwargs):
                self.target = target

            def start(self):
                self.target()

        with patch.object(services.threading, 'Thread', InlineThread), \
                patch.object(services, 'close_old_connections'), \
                self.captureOnCommitCallbacks(execute=True):
            result = services.bulk_enable(Member.objects.filter(gym=self.gym), self.admin)
        self.assertEqual(result['enabled'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(MemberAppAccount.objects.get().credentials_sent_at)
        self.assertEqual(MemberAppAccount.objects.count(), 1)

    def test_only_gym_admin_changes_settings(self):
        response = self.staff_client.patch(f'{API}admin/settings/', {'public_feed_enabled': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(MemberAppSettings.objects.get(gym=self.gym).public_feed_enabled)

        staff = CustomUser.objects.create_user(email="desk@example.com", phone_number="+919876543213",
                                               password="x" * 10, role="staff", gym=self.gym)
        client = APIClient()
        client.force_authenticate(staff)
        self.assertEqual(client.get(f'{API}admin/settings/').status_code, 200)
        self.assertEqual(client.patch(f'{API}admin/settings/', {'public_feed_enabled': False}, format='json').status_code, 403)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WebConsoleTests(TestCase):
    def setUp(self):
        self.gym = GymOffice.objects.create(name="Iron Gym", address="x", email="gym@example.com")
        self.admin = CustomUser.objects.create_user(
            email="owner@example.com", phone_number="+919876543210", password="ownerpass123",
            role="gym_admin", gym=self.gym,
        )
        self.member = Member.objects.create(
            gym=self.gym, first_name="Asha", last_name="K", mobile_number="9876543210",
            gender="Female", email="asha@example.com",
        )
        self.client.force_login(self.admin)

    def test_settings_page_saves_switches(self):
        response = self.client.get('/v5/member-api/web/settings/')
        self.assertContains(response, 'ProFit community feed')
        self.client.post('/v5/member-api/web/settings/', {'member_login_enabled': 'on', 'public_feed_enabled': 'on'})
        saved = MemberAppSettings.objects.get(gym=self.gym)
        self.assertTrue(saved.public_feed_enabled)
        self.assertFalse(saved.food_log_enabled)

    def test_member_detail_enable_resend_disable(self):
        detail = f'/v2/members/user/members/{self.member.pk}/'
        self.assertContains(self.client.get(detail), 'Enable Login')
        self.client.post(f'{detail}enable-login/')
        self.assertContains(self.client.get(detail), 'Invited')
        self.client.post(f'{detail}resend-login/')
        self.assertEqual(len(mail.outbox), 2)
        self.client.post(f'{detail}disable-login/')
        self.assertContains(self.client.get(detail), 'Turned off')
