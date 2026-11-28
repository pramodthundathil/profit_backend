import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from foodlog.models import FoodLog, FoodLogFeedback, FoodLogPhoto
from home.models import CustomUser, GymOffice
from members.models import Member
from training.models import TrainerInstruction
from .models import MemberAppAccount, MemberAppSettings

API = '/v5/member-api/'
MEDIA = tempfile.mkdtemp()
TODAY = timezone.localdate().isoformat()


def photo(name='meal.png', size=(2400, 1800), fmt='PNG'):
    buffer = BytesIO()
    Image.new('RGB', size, (200, 120, 40)).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{fmt.lower()}')


WORKOUT = {'days': [
    {'name': 'Push', 'exercises': [{'name': 'Bench press', 'sets': 4, 'reps': '8-10'}, {'name': 'Dips', 'sets': 3}]},
    {'name': 'Pull', 'exercises': [{'name': 'Rows', 'sets': 4}]},
]}


@override_settings(MEDIA_ROOT=MEDIA)
class CoachingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.gym = GymOffice.objects.create(name="Iron Gym", address="x", email="gym@example.com")
        self.trainer = CustomUser.objects.create_user(
            email="coach@example.com", phone_number="+919876543210", password="x" * 10,
            role="trainer", gym=self.gym, username="Coach Ravi",
        )
        self.other_trainer = CustomUser.objects.create_user(
            email="coach2@example.com", phone_number="+919876543211", password="x" * 10, role="trainer", gym=self.gym,
        )
        self.member_user = CustomUser.objects.create_user(
            email="asha@example.com", phone_number="+919876543212", password="memberpass1", role="member", gym=self.gym,
        )
        self.member = Member.objects.create(
            gym=self.gym, first_name="Asha", last_name="K", mobile_number="9876543212", gender="Female",
            email="asha@example.com", user=self.member_user, assigned_trainer=self.trainer,
        )
        MemberAppAccount.objects.create(member=self.member, must_change_password=False)

        self.member_client = APIClient()
        self.member_client.force_authenticate(self.member_user)
        self.coach = APIClient()
        self.coach.force_authenticate(self.trainer)

    # --- Food log ---

    def test_member_logs_meal_with_photos_and_trainer_reviews_it(self):
        response = self.member_client.post(f'{API}food-logs/', {
            'meal_type': 'lunch', 'log_date': TODAY, 'meal_time': '13:30',
            'description': 'Rice, dal, chicken', 'calories': 650, 'protein_g': '42.5',
            'photos': [photo(), photo('b.jpg', fmt='JPEG')],
        }, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['photos']), 2)
        self.assertTrue(response.data['photos'][0]['image'].startswith('http'))

        stored = Image.open(FoodLogPhoto.objects.first().image.path)
        self.assertEqual(stored.format, 'JPEG')
        self.assertLessEqual(max(stored.size), 1600)

        log_id = response.data['id']
        response = self.coach.get(f'{API}coach/members/{self.member.pk}/food-logs/?date={TODAY}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['days'][0]['meals'][0]['id'], log_id)
        self.assertEqual(response.data['days'][0]['summary']['totals']['calories'], 650)

        self.assertEqual(self.coach.get(f'{API}coach/members/').data['results'][0]['unreviewed_meals'], 1)
        response = self.coach.post(f'{API}coach/food-logs/{log_id}/feedback/', {'rating': 'great', 'comment': 'Nice protein'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.coach.get(f'{API}coach/members/').data['results'][0]['unreviewed_meals'], 0)

        response = self.member_client.get(f'{API}food-logs/?date={TODAY}')
        self.assertEqual(response.data['results'][0]['feedback'][0]['author_name'], 'Coach Ravi')
        self.assertTrue(FoodLogFeedback.objects.get().seen_by_member)

    def test_meal_needs_photo_or_description_and_at_most_four_photos(self):
        response = self.member_client.post(f'{API}food-logs/', {'meal_type': 'snack', 'log_date': TODAY}, format='multipart')
        self.assertEqual(response.status_code, 400)
        response = self.member_client.post(f'{API}food-logs/', {
            'meal_type': 'snack', 'log_date': TODAY, 'photos': [photo() for _ in range(5)],
        }, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_rejects_files_that_are_not_images(self):
        fake = SimpleUploadedFile('x.jpg', b'not an image', content_type='image/jpeg')
        response = self.member_client.post(f'{API}food-logs/', {
            'meal_type': 'snack', 'log_date': TODAY, 'photos': [fake],
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FoodLog.objects.exists())

    def test_edit_meal_removes_photo(self):
        log_id = self.member_client.post(f'{API}food-logs/', {
            'meal_type': 'dinner', 'log_date': TODAY, 'description': 'Salad', 'photos': [photo()],
        }, format='multipart').data['id']
        photo_id = FoodLogPhoto.objects.get().pk
        response = self.member_client.patch(f'{API}food-logs/{log_id}/', {'remove_photo_ids': [photo_id], 'calories': 300}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['photos'], [])
        self.assertEqual(response.data['calories'], 300)

    def test_multipart_edit_with_blank_macros_clears_them(self):
        log_id = self.member_client.post(f'{API}food-logs/', {
            'meal_type': 'lunch', 'log_date': TODAY, 'description': 'Rice', 'calories': '500', 'protein_g': '20',
        }, format='multipart').data['id']
        response = self.member_client.patch(f'{API}food-logs/{log_id}/', {
            'meal_type': 'lunch', 'log_date': TODAY, 'description': 'Rice', 'calories': '', 'protein_g': '', 'carbs_g': '', 'fat_g': '',
        }, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['calories'])
        self.assertIsNone(response.data['protein_g'])

    def test_member_cannot_see_another_members_meal(self):
        other = Member.objects.create(gym=self.gym, first_name="B", last_name="C", mobile_number="9876500000", gender="Male")
        log = FoodLog.objects.create(member=other, gym=self.gym, meal_type='lunch', log_date=TODAY, description='x')
        self.assertEqual(self.member_client.get(f'{API}food-logs/{log.pk}/').status_code, 404)

    def test_trainer_sees_only_assigned_members(self):
        client = APIClient()
        client.force_authenticate(self.other_trainer)
        self.assertEqual(client.get(f'{API}coach/members/').data['count'], 0)
        self.assertEqual(client.get(f'{API}coach/members/{self.member.pk}/food-logs/').status_code, 404)
        self.assertEqual(client.post(f'{API}coach/members/{self.member.pk}/instructions/', {
            'kind': 'note', 'title': 'Hi', 'body': 'x'}, format='json').status_code, 404)

    def test_food_log_switch_blocks_member_and_coach(self):
        MemberAppSettings.objects.update_or_create(gym=self.gym, defaults={'food_log_enabled': False})
        self.assertEqual(self.member_client.get(f'{API}food-logs/').data['code'], 'FEATURE_DISABLED')
        self.assertEqual(self.coach.get(f'{API}coach/members/{self.member.pk}/food-logs/').status_code, 403)

    # --- Instructions ---

    def test_workout_plan_flow(self):
        response = self.coach.post(f'{API}coach/members/{self.member.pk}/instructions/', {
            'kind': 'workout', 'title': 'Push/Pull', 'plan': WORKOUT,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        workout_id = response.data['id']
        exercise_id = response.data['plan']['days'][0]['exercises'][0]['id']

        plans = self.member_client.get(f'{API}instructions/').data
        self.assertEqual(plans['workout']['id'], workout_id)

        response = self.member_client.put(f'{API}instructions/{workout_id}/workout-log/', {
            'date': TODAY, 'completed': [exercise_id, 'made-up'],
        }, format='json')
        self.assertEqual(response.data['completed'], [exercise_id])
        self.assertEqual(self.member_client.get(f'{API}instructions/{workout_id}/workout-log/?date={TODAY}').data['completed'], [exercise_id])

        # Editing keeps exercise ids sent back, so ticks still match
        plan = self.coach.get(f'{API}coach/instructions/{workout_id}/').data['plan']
        plan['days'][0]['exercises'][0]['reps'] = '6-8'
        response = self.coach.patch(f'{API}coach/instructions/{workout_id}/', {'plan': plan}, format='json')
        self.assertEqual(response.data['plan']['days'][0]['exercises'][0]['id'], exercise_id)

    def test_new_active_plan_replaces_previous_one(self):
        url = f'{API}coach/members/{self.member.pk}/instructions/'
        first = self.coach.post(url, {'kind': 'diet', 'title': 'Cut', 'plan': {'calories': 1800}}, format='json').data['id']
        second = self.coach.post(url, {'kind': 'diet', 'title': 'Maintain', 'plan': {'calories': 2200}}, format='json').data['id']
        self.assertFalse(TrainerInstruction.objects.get(pk=first).is_active)
        self.assertTrue(TrainerInstruction.objects.get(pk=second).is_active)
        summary = self.member_client.get(f'{API}food-logs/').data['summary']
        self.assertEqual(summary['targets']['calories'], 2200)

    def test_plan_validation(self):
        url = f'{API}coach/members/{self.member.pk}/instructions/'
        self.assertEqual(self.coach.post(url, {'kind': 'workout', 'title': 'x', 'plan': {'days': []}}, format='json').status_code, 400)
        self.assertEqual(self.coach.post(url, {'kind': 'diet', 'title': 'x', 'plan': {}}, format='json').status_code, 400)
        self.assertEqual(self.coach.post(url, {'kind': 'note', 'title': 'x'}, format='json').status_code, 400)
        self.assertEqual(self.coach.post(url, {'kind': 'diet', 'title': 'x', 'plan': {'calories': -5}}, format='json').status_code, 400)

    def test_comment_thread(self):
        note = self.coach.post(f'{API}coach/members/{self.member.pk}/instructions/', {
            'kind': 'note', 'title': 'Hydrate', 'body': 'Drink 3L water daily',
        }, format='json').data['id']
        self.assertEqual(self.member_client.post(f'{API}instructions/{note}/comments/', {'body': 'Will do!'}, format='json').status_code, 201)
        self.coach.post(f'{API}coach/instructions/{note}/comments/', {'body': 'Great'}, format='json')
        comments = self.member_client.get(f'{API}instructions/{note}/').data['comments']
        self.assertEqual([c['from_member'] for c in comments], [True, False])
        self.assertEqual(comments[0]['author_name'], 'Asha')
        self.assertTrue(comments[0]['is_mine'])

    def test_member_with_pending_password_cannot_use_coaching(self):
        MemberAppAccount.objects.filter(member=self.member).update(must_change_password=True)
        self.assertEqual(self.member_client.get(f'{API}instructions/').data['code'], 'PASSWORD_CHANGE_REQUIRED')

    def test_admin_coaches_all_gym_members(self):
        admin = CustomUser.objects.create_user(email="owner@example.com", phone_number="+919876543219",
                                               password="x" * 10, role="gym_admin", gym=self.gym)
        client = APIClient()
        client.force_authenticate(admin)
        self.assertEqual(client.get(f'{API}coach/members/').data['count'], 1)
        self.assertEqual(client.get(f'{API}coach/members/{self.member.pk}/').status_code, 200)


@override_settings(MEDIA_ROOT=MEDIA)
class WebCoachingTests(TestCase):
    def setUp(self):
        self.gym = GymOffice.objects.create(name="Iron Gym", address="x", email="gym@example.com")
        self.trainer = CustomUser.objects.create_user(
            email="coach@example.com", phone_number="+919876543210", password="x" * 10, role="trainer", gym=self.gym,
        )
        self.member = Member.objects.create(
            gym=self.gym, first_name="Asha", last_name="K", mobile_number="9876543212", gender="Female",
            assigned_trainer=self.trainer,
        )
        self.log = FoodLog.objects.create(member=self.member, gym=self.gym, meal_type='lunch',
                                          log_date=timezone.localdate(), description='Rice and dal')
        self.client.force_login(self.trainer)
        self.base = f'{API}web/members/{self.member.pk}/coaching/'

    def test_food_tab_and_feedback(self):
        self.assertContains(self.client.get(self.base), 'Rice and dal')
        self.client.post(f'{self.base}meals/{self.log.pk}/feedback/', {'rating': 'ok', 'comment': 'Add protein'})
        self.assertEqual(FoodLogFeedback.objects.get().comment, 'Add protein')

    def test_create_workout_from_builder_and_comment(self):
        import json
        response = self.client.post(f'{self.base}instructions/new/?kind=workout', {
            'title': 'Split', 'body': '', 'start_date': TODAY, 'plan': json.dumps(WORKOUT),
        })
        self.assertEqual(response.status_code, 302)
        ins = TrainerInstruction.objects.get()
        self.assertEqual(ins.plan['days'][0]['exercises'][0]['name'], 'Bench press')
        page = self.client.get(f'{self.base}?tab=plans')
        self.assertContains(page, 'Bench press')
        self.client.post(f'{self.base}instructions/{ins.pk}/comment/', {'body': 'Start light'})
        self.assertEqual(ins.comments.get().body, 'Start light')
        self.assertContains(self.client.get(f'{self.base}instructions/{ins.pk}/'), 'Save changes')

    def test_invalid_plan_shows_error(self):
        response = self.client.post(f'{self.base}instructions/new/?kind=diet', {
            'title': 'Diet', 'start_date': TODAY, 'plan': '{}',
        })
        self.assertContains(response, 'Add a calorie target or at least one meal.')

    def test_unassigned_trainer_gets_404(self):
        other = CustomUser.objects.create_user(email="c2@example.com", phone_number="+919876543213",
                                               password="x" * 10, role="trainer", gym=self.gym)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.base).status_code, 404)
