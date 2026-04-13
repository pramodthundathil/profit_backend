from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from .models import Member, Subscription, HealthHistory, Medication, ParqForm
from home.models import GymBranch
from utils.models import Batch_DB, TypeSubscription, SubscriptionPeriod

class MemberForm(forms.ModelForm):
    """Form for creating/editing member details"""
    class Meta:
        model = Member
        exclude = ['gym', 'member_id', 'access_enabled', 'date_added', 'registration_date', 'notes']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'membership_status': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Address'}),
            'height': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'cm'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'kg'}),
            'blood_group': forms.Select(attrs={'class': 'form-select'}),
            'medical_history': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Medical History'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Name'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'id_proof': forms.FileInput(attrs={'class': 'form-control'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'access_token': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RFID/QR Token (Optional)'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super(MemberForm, self).__init__(*args, **kwargs)

        if user:
            if user.role == 'branch_admin':
                 # Branch Manager: Can only see their own branch, and it's pre-selected/hidden or read-only
                 self.fields['branch'].queryset = GymBranch.objects.filter(id=user.branch.id)
                 self.fields['branch'].initial = user.branch
                 self.fields['branch'].widget = forms.HiddenInput() # Hide it, as they can't change it
            elif user.role in ['gym_admin', 'staff']:
                # Gym Admin/Staff: Can see all active branches of their gym
                 if user.gym:
                    self.fields['branch'].queryset = GymBranch.objects.filter(gym=user.gym, is_deleted=False)
                 else:
                    self.fields['branch'].queryset = GymBranch.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        mobile_number = cleaned_data.get('mobile_number')
        
        if mobile_number and getattr(self, 'user', None) and self.user.gym:
            # Check for existing member with this mobile number in the same gym
            existing = Member.objects.filter(gym=self.user.gym, mobile_number=mobile_number)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                self.add_error('mobile_number', 'A member with this mobile number already exists in this gym.')
        
        return cleaned_data

class SubscriptionForm(forms.ModelForm):
    """Form for creating subscription details"""
    subscription_period = forms.ModelChoiceField(
        queryset=SubscriptionPeriod.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Duration"
    )
    
    payment_method = forms.ChoiceField(
        choices=(
            ("Cash", "Cash"),
            ("UPI", "UPI"),
            ("Card", "Card"),
            ("Bank Transfer", "Bank Transfer"),
            ("Tabby", "Tabby")
        ),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial="Cash"
    )
    
    # We use this to populate the duration field in model save
    
    class Meta:
        model = Subscription
        fields = [
            'subscription_type', 'subscription_period', 'start_date', 'end_date', 'status',
            'batch', 'batch_flexible', 
            'base_amount', 'discount_percentage', 'discount_amount', 'final_amount',
            'payment_terms', 'installment_count', 
            'installment_period', 'installment_period_unit',
            'amount_paid'
        ]
        widgets = {
            'subscription_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'batch_flexible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'base_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Base Amount'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '%'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Fixed Discount'}),
            'final_amount': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'installment_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'installment_period': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Interval (e.g. 1)'}),
            'installment_period_unit': forms.Select(attrs={'class': 'form-select'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Paid Amount'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        
        # If editing, make period optional as we might manually update end_date
        if self.instance.pk:
            self.fields['subscription_period'].required = False
            self.fields['amount_paid'].widget.attrs['readonly'] = True
            self.fields['amount_paid'].help_text = "Amount paid is managed via payment records"
        
        if user and user.gym:
            self.fields['subscription_type'].queryset = TypeSubscription.objects.filter(gym=user.gym, is_active=True)
            self.fields['subscription_period'].queryset = SubscriptionPeriod.objects.filter(gym=user.gym)
            self.fields['batch'].queryset = Batch_DB.objects.filter(gym=user.gym, batch_status=True)
            self.fields['batch'].required = False
        else:
            self.fields['subscription_type'].queryset = TypeSubscription.objects.none()
            self.fields['subscription_period'].queryset = SubscriptionPeriod.objects.none()
            self.fields['batch'].queryset = Batch_DB.objects.none()
            self.fields['batch'].required = False
            
        self.fields['batch'].required = False
            
        self.fields['start_date'].initial = timezone.now().date()
        self.fields['installment_count'].initial = 1
        self.fields['installment_count'].required = False
    
    def clean_installment_count(self):
        data = self.cleaned_data['installment_count']
        if not data:
            return 1
        return data

# ============================================================================
# HEALTH & MEDICAL HISTORY FORMS
# ============================================================================

class HealthHistoryForm(forms.ModelForm):
    class Meta:
        model = HealthHistory
        exclude = ['member', 'date_completed', 'last_updated']
        
        widgets = {
            'emergency_contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency Contact Name',
                'required': True
            }),
            'emergency_contact_relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Relationship (e.g., Spouse, Parent, Sibling)',
                'required': True
            }),
            'emergency_contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency Contact Phone',
                'required': True
            }),
            'emergency_contact_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Emergency Contact Address'
            }),
            'current_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Weight in KG',
                'step': '0.1',
                'required': True
            }),
            'current_height': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Height in CM',
                'step': '0.1',
                'required': True
            }),
            'fitness_goal': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'fitness_goal_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your specific fitness goals...'
            }),
            'pt_availability': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'preferred_days': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Monday, Wednesday, Friday',
                'required': True
            }),
            'physician_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Physician Name'
            }),
            'physician_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Physician Phone'
            }),
            'medical_care_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for medical care...'
            }),
            'allergies': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'List any allergies (medications, foods, environmental)...'
            }),
            'personal_asthma': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Asthma details...'
            }),
            'personal_respiratory': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Respiratory condition details...'
            }),
            'personal_diabetes_type1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type 1 diabetes details...'
            }),
            'personal_diabetes_type2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type 2 diabetes details...'
            }),
            'diabetes_duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'How long?'
            }),
            'personal_epilepsy_petite': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Petite Mal details...'
            }),
            'personal_epilepsy_grand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Grand Mal details...'
            }),
            'personal_epilepsy_other': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Other epilepsy details...'
            }),
            'personal_osteoporosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Osteoporosis details...'
            }),
            'occupational_stress': forms.Select(attrs={'class': 'form-select'}),
            'energy_level': forms.Select(attrs={'class': 'form-select'}),
            'caffeine_daily': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of caffeine beverages daily'
            }),
            'alcohol_weekly': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of alcoholic drinks weekly'
            }),
            'colds_per_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of colds per year'
            }),
            'anemia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anemia details...'
            }),
            'gastrointestinal_disorder': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'GI disorder details...'
            }),
            'hypoglycemia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hypoglycemia details...'
            }),
            'thyroid_disorder': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Thyroid disorder details...'
            }),
            'prenatal_postnatal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pre/Postnatal information...'
            }),
            'high_bp_details': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'High blood pressure details...'
            }),
            'hypertension_details': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hypertension details...'
            }),
            'high_cholesterol': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'High cholesterol details...'
            }),
            'hyperlipidemia': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Hyperlipidemia details...'
            }),
            'heart_disease': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Heart disease details...'
            }),
            'heart_attack': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Heart attack details...'
            }),
            'stroke': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Stroke details...'
            }),
            'angina': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Angina details...'
            }),
            'gout': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gout details...'
            }),
            'exercise_restrictions_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain any exercise restrictions...'
            }),
            'chest_pain_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain chest pain episodes...'
            }),
            'smoking_quit_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'head_neck_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Head/Neck issues...'
            }),
            'upper_back_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Upper back issues...'
            }),
            'shoulder_clavicle_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Shoulder/Clavicle issues...'
            }),
            'arm_elbow_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Arm/Elbow issues...'
            }),
            'wrist_hand_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Wrist/Hand issues...'
            }),
            'lower_back_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Lower back issues...'
            }),
            'hip_pelvis_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Hip/Pelvis issues...'
            }),
            'thigh_knee_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Thigh/Knee issues...'
            }),
            'arthritis_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Arthritis details...'
            }),
            'hernia_details': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hernia details...'
            }),
            'surgeries_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Previous surgeries details...'
            }),
            'other_musculoskeletal': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Other musculoskeletal issues...'
            }),
            'diet_plan_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Diet plan details...'
            }),
            'supplements_list': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'List supplements...'
            }),
            'weight_change_amount': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., +5kg or -3kg'
            }),
            'weight_change_duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2 months, 6 weeks'
            }),
            'caffeine_beverages_daily': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of beverages'
            }),
            'nutritional_habits_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your current nutritional habits...'
            }),
            'food_allergies_issues': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Food allergies, meal times, etc...'
            }),
            'work_exercise_habits': forms.Select(attrs={'class': 'form-select'}),
            'work_stress_level': forms.Select(attrs={'class': 'form-select'}),
            'home_stress_level': forms.Select(attrs={'class': 'form-select'}),
            'additional_comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Any additional comments pertinent to your exercise program...'
            }),

            'has_risky_heart_conditions': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'risky_heart_conditions_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please explain specific heart/cardiovascular conditions...'
            }),
            'has_risky_health_conditions': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'risky_health_conditions_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please explain other health conditions that may be risky...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mark mandatory fields
        mandatory_fields = [
            'emergency_contact_name', 'emergency_contact_relationship', 
            'emergency_contact_phone', 'current_weight', 'current_height', 
            'fitness_goal', 'pt_availability', 'preferred_days'
        ]
        
        for field_name in mandatory_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
                if 'placeholder' in self.fields[field_name].widget.attrs:
                    self.fields[field_name].widget.attrs['placeholder'] += ' *'

class MedicationForm(forms.ModelForm):
    class Meta:
        model = Medication
        exclude = ['health_history']
        widgets = {
            'medication_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Medication name/type'
            }),
            'dosage_frequency': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10mg twice daily'
            }),
            'reason_for_taking': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reason for taking this medication'
            }),
        }

# Create formset for medications
MedicationFormSet = inlineformset_factory(
    HealthHistory, 
    Medication, 
    form=MedicationForm,
    extra=3,
    can_delete=True
)

class ParqFormModelForm(forms.ModelForm):
    class Meta:
        model = ParqForm
        fields = [
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_mobile',
            'heart_condition',
            'chest_pain_activity',
            'chest_pain_last_month',
            'lose_consciousness',
            'bone_joint_problem',
            'medical_conditions',
            'medical_conditions_specify',
            'current_treatment',
            'current_treatment_specify',
            'other_reason',
            'other_reason_specify',
            'participant_signature',
            'parent_guardian_signature',
            'tutor_signature',
            'participant_signature_date',
            'parent_guardian_signature_date',
            'tutor_signature_date'
        ]
        
        widgets = {
            'emergency_contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency Contact Name'
            }),
            'emergency_contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency Contact Phone'
            }),
            'emergency_contact_mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency Contact Mobile'
            }),
            'medical_conditions_specify': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please specify medical conditions'
            }),
            'current_treatment_specify': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please specify current treatment'
            }),
            'other_reason_specify': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please specify other reasons'
            }),
            'participant_signature': forms.HiddenInput(),
            'parent_guardian_signature': forms.HiddenInput(),
            'tutor_signature': forms.HiddenInput(),
            'participant_signature_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'parent_guardian_signature_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tutor_signature_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'heart_condition': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'chest_pain_activity': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'chest_pain_last_month': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'lose_consciousness': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bone_joint_problem': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'medical_conditions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'current_treatment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_reason': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ParqUpdateForm(forms.ModelForm):
    class Meta:
        model = ParqForm
        fields = '__all__'
        exclude = ['member', 'created_at', 'updated_at']
        widgets = {
            'heart_condition': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Add other widgets as needed
        }
