"""Health history and PAR-Q forms in the member app.

Each form is described as sections of fields so the app can draw it without hard-coding
dozens of questions. A form can be submitted once; after that it is read-only for the member
(gym staff can still correct it in the web console).
"""
from django.db import transaction
from django.db.models import BooleanField, DateField, FloatField, IntegerField, TextField
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from members.forms import HealthHistoryForm, ParqFormModelForm
from members.models import HealthHistory, Medication, ParqForm
from .permissions import IsAppMember

TAG = 'Member App - Health forms'

# Each field: name, or (name, {overrides}). Overrides: label, show_if (a yes/no field), unit, required.
HEALTH_SECTIONS = [
    ('Emergency contact', 'Who should we call if something happens at the gym?', [
        ('emergency_contact_name', {'label': 'Name', 'required': True}),
        ('emergency_contact_relationship', {'label': 'Relationship', 'required': True}),
        ('emergency_contact_phone', {'label': 'Phone', 'required': True, 'keyboard': 'phone'}),
        ('emergency_contact_address', {'label': 'Address'}),
    ]),
    ('Body and goals', None, [
        ('current_weight', {'label': 'Weight', 'unit': 'kg', 'required': True}),
        ('current_height', {'label': 'Height', 'unit': 'cm', 'required': True}),
        ('fitness_goal', {'label': 'Main fitness goal', 'required': True}),
        ('fitness_goal_details', {'label': 'Tell us more about your goal'}),
        ('pt_availability', {'label': 'When can you train?', 'required': True}),
        ('preferred_days', {'label': 'Preferred days', 'required': True}),
    ]),
    ('Doctor and medication', None, [
        ('physician_name', {'label': "Doctor's name"}),
        ('physician_phone', {'label': "Doctor's phone", 'keyboard': 'phone'}),
        ('under_medical_care', {'label': 'Are you under medical care now?'}),
        ('medical_care_reason', {'label': 'What for?', 'show_if': 'under_medical_care'}),
        ('taking_medications', {'label': 'Do you take any medication?'}),
        ('medications', {'label': 'Your medication', 'type': 'medications', 'show_if': 'taking_medications'}),
        ('allergies', {'label': 'Allergies'}),
    ]),
    ('Health check', 'Answer yes if any of these apply to you.', [
        ('high_blood_pressure', {'label': 'High blood pressure'}),
        ('bone_joint_problems', {'label': 'Bone or joint problems'}),
        ('over_65', {'label': 'Over 65 years old'}),
        ('unaccustomed_exercise', {'label': 'Not used to exercise'}),
        ('has_risky_heart_conditions', {'label': 'Heart conditions (heart disease, irregular heartbeat, past heart attack or stroke)'}),
        ('risky_heart_conditions_details', {'label': 'Please explain', 'show_if': 'has_risky_heart_conditions'}),
        ('has_risky_health_conditions', {'label': 'Other conditions that could make exercise risky (breathing, joints, metabolic, neurological)'}),
        ('risky_health_conditions_details', {'label': 'Please explain', 'show_if': 'has_risky_health_conditions'}),
        ('chest_pain_exercise', {'label': 'Chest pain when exercising'}),
        ('chest_pain_details', {'label': 'Please explain', 'show_if': 'chest_pain_exercise'}),
        ('exercise_restrictions', {'label': 'Has a doctor restricted your exercise?'}),
        ('exercise_restrictions_details', {'label': 'What restrictions?', 'show_if': 'exercise_restrictions'}),
    ]),
    ('Medical history', 'Tick family history; describe anything you have had yourself.', [
        ('family_asthma', {'label': 'Asthma in your family'}),
        ('personal_asthma', {'label': 'Your asthma (if any)'}),
        ('family_respiratory', {'label': 'Breathing problems in your family'}),
        ('personal_respiratory', {'label': 'Your breathing problems (if any)'}),
        ('family_diabetes', {'label': 'Diabetes in your family'}),
        ('personal_diabetes_type1', {'label': 'Your type 1 diabetes (if any)'}),
        ('personal_diabetes_type2', {'label': 'Your type 2 diabetes (if any)'}),
        ('diabetes_duration', {'label': 'How long have you had diabetes?'}),
        ('family_epilepsy', {'label': 'Epilepsy in your family'}),
        ('personal_epilepsy_petite', {'label': 'Your petit mal seizures (if any)'}),
        ('personal_epilepsy_grand', {'label': 'Your grand mal seizures (if any)'}),
        ('personal_epilepsy_other', {'label': 'Other seizures (if any)'}),
        ('family_osteoporosis', {'label': 'Osteoporosis in your family'}),
        ('personal_osteoporosis', {'label': 'Your osteoporosis (if any)'}),
        ('anemia', {'label': 'Anaemia'}),
        ('gastrointestinal_disorder', {'label': 'Stomach or bowel problems'}),
        ('hypoglycemia', {'label': 'Low blood sugar (hypoglycaemia)'}),
        ('thyroid_disorder', {'label': 'Thyroid problems'}),
        ('prenatal_postnatal', {'label': 'Pregnant or recently given birth'}),
    ]),
    ('Heart and circulation', 'Leave blank if none apply.', [
        ('high_bp_details', {'label': 'High blood pressure'}),
        ('hypertension_details', {'label': 'Hypertension'}),
        ('high_cholesterol', {'label': 'High cholesterol'}),
        ('hyperlipidemia', {'label': 'Hyperlipidaemia'}),
        ('heart_disease', {'label': 'Heart disease'}),
        ('heart_attack', {'label': 'Heart attack'}),
        ('stroke', {'label': 'Stroke'}),
        ('angina', {'label': 'Angina'}),
        ('gout', {'label': 'Gout'}),
    ]),
    ('Lifestyle', None, [
        ('occupational_stress', {'label': 'Stress at work'}),
        ('energy_level', {'label': 'Energy level'}),
        ('caffeine_daily', {'label': 'Cups of coffee or tea a day'}),
        ('alcohol_weekly', {'label': 'Alcoholic drinks a week'}),
        ('colds_per_year', {'label': 'Colds a year'}),
        ('smoking_status', {'label': 'Smoking'}),
        ('smoking_quit_date', {'label': 'If you quit, when?'}),
    ]),
    ('Muscles and joints', 'Describe any pain, injuries or problems. Leave blank if none.', [
        ('head_neck_issues', {'label': 'Head or neck'}),
        ('upper_back_issues', {'label': 'Upper back'}),
        ('shoulder_clavicle_issues', {'label': 'Shoulder or collarbone'}),
        ('arm_elbow_issues', {'label': 'Arm or elbow'}),
        ('wrist_hand_issues', {'label': 'Wrist or hand'}),
        ('lower_back_issues', {'label': 'Lower back'}),
        ('hip_pelvis_issues', {'label': 'Hip or pelvis'}),
        ('thigh_knee_issues', {'label': 'Thigh or knee'}),
        ('arthritis_details', {'label': 'Arthritis'}),
        ('hernia_details', {'label': 'Hernia'}),
        ('surgeries_details', {'label': 'Past surgeries'}),
        ('other_musculoskeletal', {'label': 'Anything else'}),
    ]),
    ('Food and nutrition', None, [
        ('on_diet_plan', {'label': 'Are you on a diet plan?'}),
        ('diet_plan_details', {'label': 'Which plan?', 'show_if': 'on_diet_plan'}),
        ('taking_supplements', {'label': 'Do you take supplements?'}),
        ('supplements_list', {'label': 'Which supplements?', 'show_if': 'taking_supplements'}),
        ('weight_fluctuations', {'label': 'Does your weight go up and down a lot?'}),
        ('recent_weight_change', {'label': 'Has your weight changed recently?'}),
        ('weight_change_amount', {'label': 'By how much?', 'show_if': 'recent_weight_change'}),
        ('weight_change_duration', {'label': 'Over how long?', 'show_if': 'recent_weight_change'}),
        ('caffeine_beverages_daily', {'label': 'Caffeine drinks a day'}),
        ('nutritional_habits_description', {'label': 'Describe how you usually eat'}),
        ('food_allergies_issues', {'label': 'Food allergies or intolerances'}),
    ]),
    ('Work and stress', None, [
        ('work_exercise_habits', {'label': 'How active are you at work and in free time?'}),
        ('work_stress_level', {'label': 'Stress at work'}),
        ('home_stress_level', {'label': 'Stress at home'}),
        ('works_over_40_hours', {'label': 'Do you work more than 40 hours a week?'}),
        ('additional_comments', {'label': 'Anything else your trainer should know?'}),
    ]),
]

PARQ_SECTIONS = [
    ('Emergency contact', None, [
        ('emergency_contact_name', {'label': 'Name', 'required': True}),
        ('emergency_contact_phone', {'label': 'Phone', 'required': True, 'keyboard': 'phone'}),
        ('emergency_contact_mobile', {'label': 'Mobile', 'keyboard': 'phone'}),
    ]),
    ('Questions', 'Answer each question honestly. If you answer yes to any, your gym may ask for a note from your doctor.', [
        'heart_condition',
        'chest_pain_activity',
        'chest_pain_last_month',
        'lose_consciousness',
        'bone_joint_problem',
        'medical_conditions',
        ('medical_conditions_specify', {'label': 'Which conditions?', 'show_if': 'medical_conditions'}),
        'current_treatment',
        ('current_treatment_specify', {'label': 'What treatment?', 'show_if': 'current_treatment'}),
        'other_reason',
        ('other_reason_specify', {'label': 'What reason?', 'show_if': 'other_reason'}),
    ]),
    ('Declaration', 'I have read, understood and answered this questionnaire truthfully.', [
        ('participant_signature', {'label': 'Your signature', 'type': 'signature', 'required': True}),
    ]),
]

FORMS = {
    'health_history': {
        'title': 'Health history',
        'description': 'Your health, goals and lifestyle, so your trainer can plan safely.',
        'model': HealthHistory,
        'sections': HEALTH_SECTIONS,
    },
    'parq': {
        'title': 'PAR-Q',
        'description': 'Physical activity readiness questions to check you can exercise safely.',
        'model': ParqForm,
        'sections': PARQ_SECTIONS,
    },
}


def _field_type(model_field):
    if model_field.choices:
        return 'choice'
    if isinstance(model_field, BooleanField):
        return 'boolean'
    if isinstance(model_field, (IntegerField,)):
        return 'integer'
    if isinstance(model_field, FloatField):
        return 'number'
    if isinstance(model_field, DateField):
        return 'date'
    if isinstance(model_field, TextField):
        return 'textarea'
    return 'text'


def _describe(model, entry):
    name, overrides = (entry, {}) if isinstance(entry, str) else entry
    if overrides.get('type') == 'medications':
        return {'name': name, 'type': 'medications', 'label': overrides['label'], 'required': False,
                'show_if': overrides.get('show_if')}
    field = model._meta.get_field(name)
    kind = overrides.get('type') or _field_type(field)
    label = overrides.get('label') or (field.help_text if kind == 'boolean' and field.help_text else field.verbose_name.capitalize())
    return {
        'name': name,
        'type': kind,
        'label': label,
        'required': overrides.get('required', False),
        'choices': [{'value': v, 'label': l} for v, l in field.choices] if field.choices else None,
        'max_length': getattr(field, 'max_length', None),
        'unit': overrides.get('unit'),
        'keyboard': overrides.get('keyboard'),
        'show_if': overrides.get('show_if'),
    }


def schema(key):
    spec = FORMS[key]
    return [
        {'title': title, 'description': description, 'fields': [_describe(spec['model'], entry) for entry in fields]}
        for title, description, fields in spec['sections']
    ]


def _instance(member, key):
    if key == 'health_history':
        return HealthHistory.objects.filter(member=member).first()
    return ParqForm.objects.filter(member=member).first()


def _submitted(key, instance):
    if instance is None:
        return False
    return instance.is_completed if key == 'parq' else True


def _submitted_at(key, instance):
    if not _submitted(key, instance):
        return None
    return instance.created_at if key == 'parq' else instance.date_completed


def _values(key, instance):
    if instance is None:
        return {}
    values = {}
    for section in schema(key):
        for field in section['fields']:
            if field['type'] == 'medications':
                values['medications'] = list(instance.medications.values('medication_type', 'dosage_frequency', 'reason_for_taking'))
                continue
            value = getattr(instance, field['name'])
            values[field['name']] = value.isoformat() if hasattr(value, 'isoformat') else value
    return values


class HealthFormListView(APIView):
    permission_classes = [IsAppMember]

    @swagger_auto_schema(tags=[TAG], operation_description="The health forms and whether each one is submitted")
    def get(self, request):
        member = request.member
        items = []
        for key, spec in FORMS.items():
            instance = _instance(member, key)
            items.append({
                'key': key,
                'title': spec['title'],
                'description': spec['description'],
                'submitted': _submitted(key, instance),
                'submitted_at': _submitted_at(key, instance),
                # The gym asks for a PAR-Q when the health history shows a risk.
                'recommended': key == 'parq' and member.risk_medical and not _submitted(key, instance),
            })
        return Response(items)


class HealthFormView(APIView):
    permission_classes = [IsAppMember]

    @swagger_auto_schema(tags=[TAG], operation_description="A form's sections and fields, plus answers once submitted")
    def get(self, request, key):
        if key not in FORMS:
            return Response({'error': 'Form not found.'}, status=status.HTTP_404_NOT_FOUND)
        instance = _instance(request.member, key)
        locked = _submitted(key, instance)
        return Response({
            'key': key,
            'title': FORMS[key]['title'],
            'description': FORMS[key]['description'],
            'locked': locked,
            'submitted_at': _submitted_at(key, instance),
            'sections': schema(key),
            'values': _values(key, instance) if locked else {},
        })

    @swagger_auto_schema(tags=[TAG], operation_description="Submit the form once. Body: {field: value, ..., medications: [...]}")
    def post(self, request, key):
        if key not in FORMS:
            return Response({'error': 'Form not found.'}, status=status.HTTP_404_NOT_FOUND)
        member = request.member
        instance = _instance(member, key)
        if _submitted(key, instance):
            return Response(
                {'error': 'You have already submitted this form. Ask your gym if something needs changing.'},
                status=status.HTTP_409_CONFLICT,
            )

        data = {k: v for k, v in request.data.items() if v is not None and k != 'medications'}
        # Django forms read unticked checkboxes as missing, so drop false values.
        data = {k: v for k, v in data.items() if v is not False}
        if key == 'parq' and not str(data.get('participant_signature') or '').startswith('data:image/'):
            return Response({'participant_signature': ['Please sign the form.']}, status=status.HTTP_400_BAD_REQUEST)

        form_class = HealthHistoryForm if key == 'health_history' else ParqFormModelForm
        form = form_class(data=data, instance=instance)
        if not form.is_valid():
            return Response({name: [str(e) for e in errors] for name, errors in form.errors.items()}, status=status.HTTP_400_BAD_REQUEST)

        medications = []
        if key == 'health_history' and form.cleaned_data.get('taking_medications'):
            for item in request.data.get('medications') or []:
                if not isinstance(item, dict):
                    continue
                med = {f: str(item.get(f) or '').strip()[:500] for f in ('medication_type', 'dosage_frequency', 'reason_for_taking')}
                if med['medication_type']:
                    medications.append(med)

        with transaction.atomic():
            saved = form.save(commit=False)
            saved.member = member
            if key == 'parq':
                saved.is_completed = True
                saved.participant_signature_date = saved.participant_signature_date or timezone.localdate()
            saved.save()
            if key == 'health_history':
                saved.medications.all().delete()
                Medication.objects.bulk_create([Medication(health_history=saved, **m) for m in medications])
                member.risk_medical = saved.has_risky_heart_conditions or saved.has_risky_health_conditions
                member.save(update_fields=['risk_medical'])

        next_form = None
        if key == 'health_history' and member.risk_medical and not _submitted('parq', _instance(member, 'parq')):
            next_form = 'parq'
        return Response({'message': 'Thank you. Your form has been sent to your gym.', 'next_form': next_form}, status=status.HTTP_201_CREATED)
