from django.test import TestCase
from rest_framework.test import APIClient

from home.models import CustomUser, GymOffice
from members.models import HealthHistory, Member, ParqForm
from .models import MemberAppAccount

API = '/v5/member-api/forms/'
SIGNATURE = 'data:image/svg+xml;base64,PHN2Zy8+'

HEALTH = {
    'emergency_contact_name': 'Ravi', 'emergency_contact_relationship': 'Brother', 'emergency_contact_phone': '9876543210',
    'current_weight': 70, 'current_height': 172, 'fitness_goal': 'weight_loss', 'pt_availability': 'morning',
    'preferred_days': 'Mon, Wed', 'taking_medications': True, 'has_risky_heart_conditions': True,
    'risky_heart_conditions_details': 'Irregular heartbeat', 'high_blood_pressure': False,
    'medications': [{'medication_type': 'Aspirin', 'dosage_frequency': 'Daily', 'reason_for_taking': 'Heart'}],
}


class HealthFormTests(TestCase):
    def setUp(self):
        gym = GymOffice.objects.create(name="Iron Gym", address="x", email="gym@example.com")
        user = CustomUser.objects.create_user(email="asha@example.com", phone_number="+919876543212",
                                              password="memberpass1", role="member", gym=gym)
        self.member = Member.objects.create(gym=gym, first_name="Asha", last_name="K", mobile_number="9876543212",
                                            gender="Female", email=user.email, user=user)
        MemberAppAccount.objects.create(member=self.member, must_change_password=False)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_schema_lists_sections_and_choices(self):
        data = self.client.get(f'{API}health_history/').data
        self.assertFalse(data['locked'])
        fields = {f['name']: f for s in data['sections'] for f in s['fields']}
        self.assertEqual(fields['fitness_goal']['type'], 'choice')
        self.assertEqual(fields['medications']['show_if'], 'taking_medications')
        self.assertEqual(fields['current_weight']['unit'], 'kg')
        parq = self.client.get(f'{API}parq/').data
        q = {f['name']: f for s in parq['sections'] for f in s['fields']}
        self.assertEqual(q['heart_condition']['label'], 'Has your doctor ever said that you have a heart condition?')

    def test_submit_health_history_once_then_locked(self):
        response = self.client.post(f'{API}health_history/', HEALTH, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['next_form'], 'parq')  # risky answer asks for a PAR-Q
        history = HealthHistory.objects.get(member=self.member)
        self.assertEqual(history.medications.get().medication_type, 'Aspirin')
        self.member.refresh_from_db()
        self.assertTrue(self.member.risk_medical)

        data = self.client.get(f'{API}health_history/').data
        self.assertTrue(data['locked'])
        self.assertEqual(data['values']['emergency_contact_name'], 'Ravi')
        self.assertEqual(data['values']['medications'][0]['dosage_frequency'], 'Daily')

        again = self.client.post(f'{API}health_history/', {**HEALTH, 'emergency_contact_name': 'Changed'}, format='json')
        self.assertEqual(again.status_code, 409)
        self.assertEqual(HealthHistory.objects.get(member=self.member).emergency_contact_name, 'Ravi')

        forms = {f['key']: f for f in self.client.get(API).data}
        self.assertTrue(forms['health_history']['submitted'])
        self.assertTrue(forms['parq']['recommended'])

    def test_required_fields(self):
        response = self.client.post(f'{API}health_history/', {'emergency_contact_name': 'Ravi'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(HealthHistory.objects.exists())

    def test_parq_needs_signature_and_locks(self):
        body = {'emergency_contact_name': 'Ravi', 'emergency_contact_phone': '98765', 'heart_condition': True}
        self.assertEqual(self.client.post(f'{API}parq/', body, format='json').status_code, 400)
        response = self.client.post(f'{API}parq/', {**body, 'participant_signature': SIGNATURE}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        parq = ParqForm.objects.get(member=self.member)
        self.assertTrue(parq.is_completed)
        self.assertTrue(parq.requires_doctor_consent)
        self.assertIsNotNone(parq.participant_signature_date)
        self.assertEqual(self.client.post(f'{API}parq/', {**body, 'participant_signature': SIGNATURE}, format='json').status_code, 409)

    def test_public_link_locked_after_submit(self):
        self.client.post(f'{API}health_history/', HEALTH, format='json')
        response = self.client.get(f'/v2/members/public/health-history/{self.member.public_token}/')
        self.assertEqual(response.status_code, 302)
