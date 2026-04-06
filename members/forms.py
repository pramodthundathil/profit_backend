from django import forms
from django.utils import timezone
from .models import Member, Subscription
from home.models import GymBranch
from utils.models import Batch_DB, TypeSubscription, SubscriptionPeriod

class MemberForm(forms.ModelForm):
    """Form for creating/editing member details"""
    class Meta:
        model = Member
        exclude = ['gym', 'member_id', 'membership_status', 'access_enabled', 'date_added', 'registration_date', 'notes', 'is_active']
        widgets = {
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
            'subscription_type', 'subscription_period', 'start_date', 
            'batch', 'batch_flexible', 
            'base_amount', 'discount_percentage', 'discount_amount', 'final_amount',
            'payment_terms', 'installment_count', 'amount_paid'
        ]
        widgets = {
            'subscription_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'batch_flexible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'base_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Base Amount'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '%'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Fixed Discount'}),
            'final_amount': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'installment_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Paid Amount'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        
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
