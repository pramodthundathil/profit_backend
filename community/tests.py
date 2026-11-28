import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from home.models import CustomUser, GymOffice
from member_api.models import MemberAppAccount, MemberAppSettings
from members.models import Member
from .models import Post, PostLike, SocialProfile, UserBlock

API = '/v5/member-api/'
MEDIA = tempfile.mkdtemp()


def photo():
    buffer = BytesIO()
    Image.new('RGB', (800, 600), (10, 120, 200)).save(buffer, 'PNG')
    return SimpleUploadedFile('p.png', buffer.getvalue(), content_type='image/png')


_phone = iter(range(9000000000, 9100000000))


def make_member(gym, first, trainer=None):
    user = CustomUser.objects.create_user(
        email=f"{first.lower()}@{gym.email.split('@')[0]}.example.com", phone_number=f"+91{next(_phone)}",
        password="memberpass1", role="member", gym=gym,
    )
    member = Member.objects.create(
        gym=gym, first_name=first, last_name="Secret", mobile_number=str(next(_phone)), gender="Female",
        email=user.email, user=user, assigned_trainer=trainer,
    )
    MemberAppAccount.objects.create(member=member, must_change_password=False)
    client = APIClient()
    client.force_authenticate(user)
    return member, client


@override_settings(MEDIA_ROOT=MEDIA)
class CommunityTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.gym = GymOffice.objects.create(name="Iron Gym", address="x", email="iron@example.com")
        self.other_gym = GymOffice.objects.create(name="Steel Gym", address="x", email="steel@example.com")
        for gym in (self.gym, self.other_gym):
            MemberAppSettings.objects.create(gym=gym, public_feed_enabled=True)
        self.asha, self.asha_client = make_member(self.gym, "Asha")
        self.ben, self.ben_client = make_member(self.gym, "Ben")
        self.cara, self.cara_client = make_member(self.other_gym, "Cara")

    def post(self, client, **data):
        data.setdefault('text', 'Leg day done!')
        return client.post(f'{API}community/posts/', data, format='multipart')

    def feed(self, client, scope):
        return client.get(f'{API}community/feed/?scope={scope}').data['results']

    def test_gym_post_stays_in_gym_and_public_post_reaches_everyone(self):
        gym_post = self.post(self.asha_client, visibility='gym').data['id']
        public_post = self.post(self.asha_client, visibility='public', photos=[photo()]).data['id']

        self.assertEqual([p['id'] for p in self.feed(self.ben_client, 'gym')], [public_post, gym_post])
        self.assertEqual([p['id'] for p in self.feed(self.cara_client, 'public')], [public_post])
        self.assertEqual(self.feed(self.cara_client, 'gym'), [])
        self.assertEqual(self.cara_client.get(f'{API}community/posts/{gym_post}/').status_code, 404)

    def test_public_feed_shows_display_name_only(self):
        SocialProfile.objects.update_or_create(member=self.asha, defaults={'display_name': 'IronQueen'})
        self.post(self.asha_client, visibility='public')
        post = self.feed(self.cara_client, 'public')[0]
        self.assertEqual(post['author']['display_name'], 'IronQueen')
        flat = str(post)
        self.assertNotIn('Secret', flat)
        self.assertNotIn('Iron Gym', flat)
        self.assertNotIn('asha@', flat)

    def test_gym_switches(self):
        MemberAppSettings.objects.filter(gym=self.other_gym).update(public_feed_enabled=False)
        self.post(self.asha_client, visibility='public')
        self.assertEqual(self.feed(self.cara_client, 'public'), [])  # viewer's gym is off
        response = self.post(self.cara_client, visibility='public')
        self.assertEqual(response.status_code, 400)

        MemberAppSettings.objects.filter(gym=self.other_gym).update(community_feed_enabled=False)
        self.assertEqual(self.cara_client.get(f'{API}community/feed/').data['code'], 'FEATURE_DISABLED')

    def test_posts_of_gym_that_turned_public_off_leave_public_feed(self):
        self.post(self.asha_client, visibility='public')
        MemberAppSettings.objects.filter(gym=self.gym).update(public_feed_enabled=False)
        self.assertEqual(self.feed(self.cara_client, 'public'), [])

    def test_approval_flow(self):
        MemberAppSettings.objects.filter(gym=self.gym).update(require_post_approval=True)
        post_id = self.post(self.asha_client).data['id']
        self.assertEqual(self.feed(self.ben_client, 'gym'), [])
        self.assertEqual(self.feed(self.asha_client, 'gym')[0]['status'], 'pending')

        trainer = CustomUser.objects.create_user(email="t@example.com", phone_number="+919811111111",
                                                 password="x" * 10, role="trainer", gym=self.gym)
        coach = APIClient()
        coach.force_authenticate(trainer)
        queue = coach.get(f'{API}coach/community/posts/?filter=pending').data
        self.assertEqual(queue['counts']['pending'], 1)
        self.assertEqual(queue['results'][0]['member']['full_name'], 'Asha Secret')
        coach.post(f'{API}coach/community/posts/{post_id}/moderate/', {'action': 'approve'}, format='json')
        self.assertEqual(len(self.feed(self.ben_client, 'gym')), 1)

    def test_other_gym_staff_cannot_moderate(self):
        post_id = self.post(self.asha_client, visibility='public').data['id']
        admin = CustomUser.objects.create_user(email="a@steel.example.com", phone_number="+919822222222",
                                               password="x" * 10, role="gym_admin", gym=self.other_gym)
        client = APIClient()
        client.force_authenticate(admin)
        self.assertEqual(client.post(f'{API}coach/community/posts/{post_id}/moderate/', {'action': 'hide'}, format='json').status_code, 404)

    def test_like_comment_and_counts(self):
        post_id = self.post(self.asha_client).data['id']
        self.ben_client.post(f'{API}community/posts/{post_id}/like/')
        self.ben_client.post(f'{API}community/posts/{post_id}/like/')  # twice counts once
        self.assertEqual(Post.objects.get(pk=post_id).like_count, 1)
        self.assertTrue(self.feed(self.ben_client, 'gym')[0]['liked_by_me'])
        self.ben_client.delete(f'{API}community/posts/{post_id}/like/')
        self.assertEqual(Post.objects.get(pk=post_id).like_count, 0)

        comment = self.ben_client.post(f'{API}community/posts/{post_id}/comments/', {'text': 'Beast!'}, format='json').data
        detail = self.asha_client.get(f'{API}community/posts/{post_id}/').data
        self.assertEqual(detail['comment_count'], 1)
        self.assertTrue(detail['comments'][0]['can_delete'])  # post author can remove comments on their post
        self.assertEqual(self.asha_client.delete(f'{API}community/comments/{comment["id"]}/').status_code, 204)
        self.assertEqual(Post.objects.get(pk=post_id).comment_count, 0)

    def test_three_reports_hide_post(self):
        post_id = self.post(self.asha_client, visibility='public').data['id']
        dan, dan_client = make_member(self.gym, "Dan")
        for client in (self.ben_client, self.cara_client, self.cara_client, dan_client):
            client.post(f'{API}community/posts/{post_id}/report/', {'reason': 'spam'}, format='json')
        post = Post.objects.get(pk=post_id)
        self.assertEqual(post.status, Post.HIDDEN)
        self.assertEqual(post.report_count, 3)
        self.assertEqual(self.feed(self.ben_client, 'gym'), [])
        self.assertEqual(self.feed(self.asha_client, 'gym')[0]['status'], 'hidden')

    def test_block_hides_posts_both_ways(self):
        self.post(self.asha_client)
        self.post(self.ben_client)
        ben_profile = SocialProfile.for_member(self.ben)
        self.asha_client.post(f'{API}community/profiles/{ben_profile.pk}/block/')
        self.assertTrue(all(p['author']['is_me'] for p in self.feed(self.asha_client, 'gym')))
        self.assertTrue(all(p['author']['is_me'] for p in self.feed(self.ben_client, 'gym')))
        # The blocker can still open the profile to unblock
        self.assertTrue(self.asha_client.get(f'{API}community/profiles/{ben_profile.pk}/').data['blocked'])
        self.asha_client.delete(f'{API}community/profiles/{ben_profile.pk}/block/')
        self.assertFalse(UserBlock.objects.exists())

    def test_profile_of_other_gym_member_only_via_public_posts(self):
        cara_profile = SocialProfile.for_member(self.cara)
        self.assertEqual(self.asha_client.get(f'{API}community/profiles/{cara_profile.pk}/').status_code, 404)
        self.post(self.cara_client, visibility='public')
        response = self.asha_client.get(f'{API}community/profiles/{cara_profile.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['posts']), 1)

    def test_edit_my_profile_and_avatar(self):
        response = self.asha_client.patch(f'{API}community/me/', {'display_name': '  Asha   Lifts ', 'avatar': photo()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['display_name'], 'Asha Lifts')
        self.assertTrue(response.data['avatar'].startswith('http'))

    def test_post_needs_text_or_photo_and_owner_can_delete(self):
        self.assertEqual(self.post(self.asha_client, text='').status_code, 400)
        post_id = self.post(self.asha_client).data['id']
        self.assertEqual(self.ben_client.delete(f'{API}community/posts/{post_id}/').status_code, 404)
        self.assertEqual(self.asha_client.delete(f'{API}community/posts/{post_id}/').status_code, 204)

    def test_disabled_member_posts_disappear(self):
        self.post(self.ben_client)
        CustomUser.objects.filter(pk=self.ben.user_id).update(is_active=False)
        self.assertEqual(self.feed(self.asha_client, 'gym'), [])

    def test_pagination(self):
        for i in range(25):
            Post.objects.create(gym=self.gym, author=self.asha.user, text=f'p{i}')
        first = self.asha_client.get(f'{API}community/feed/').data
        self.assertEqual(len(first['results']), 20)
        second = self.asha_client.get(f"{API}community/feed/?before={first['next_before']}").data
        self.assertEqual(len(second['results']), 5)
        self.assertIsNone(second['next_before'])

    def test_config_has_trainer_and_display_name(self):
        trainer = CustomUser.objects.create_user(email="coach@example.com", phone_number="+919833333333",
                                                 password="x" * 10, role="trainer", gym=self.gym, username="Coach Ravi")
        Member.objects.filter(pk=self.asha.pk).update(assigned_trainer=trainer)
        config = self.asha_client.get(f'{API}config/').data
        self.assertEqual(config['trainer']['name'], 'Coach Ravi')
        self.assertEqual(config['social_profile']['display_name'], 'Asha')
        self.assertIn('days_left', config['membership'])


@override_settings(MEDIA_ROOT=MEDIA)
class WebModerationTests(TestCase):
    def test_trainer_approves_from_web(self):
        gym = GymOffice.objects.create(name="Iron Gym", address="x", email="iron@example.com")
        member, _ = make_member(gym, "Asha")
        post = Post.objects.create(gym=gym, author=member.user, text="Hello", status=Post.PENDING)
        trainer = CustomUser.objects.create_user(email="t@example.com", phone_number="+919844444444",
                                                 password="x" * 10, role="trainer", gym=gym)
        self.client.force_login(trainer)
        page = self.client.get('/v5/member-api/web/community/')
        self.assertContains(page, 'Asha Secret')
        self.client.post('/v5/member-api/web/community/', {'post_id': post.pk, 'action': 'approve'})
        post.refresh_from_db()
        self.assertEqual(post.status, Post.PUBLISHED)
