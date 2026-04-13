from .models import GymOffice, GymBranch, CustomUser
from django import forms

class GymOfficeForm(forms.ModelForm):
    class Meta:
        model = GymOffice
        fields = ['name', 'address', 'email', 'phone', 'logo', 'is_active', 'license_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'license_key': forms.Select(attrs={'class': 'form-select'}),
        }

class GymOfficeSettingsForm(forms.ModelForm):
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee (₹)'),
        ('USD', 'US Dollar ($)'),
        ('AED', 'UAE Dirham (AED)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('SAR', 'Saudi Riyal (SR)'),
        ('QAR', 'Qatari Rial (QR)'),
        ('KWD', 'Kuwaiti Dinar (KD)'),
        ('BHD', 'Bahraini Dinar (BD)'),
        ('OMR', 'Omani Rial (RO)'),
    ]
    
    currency_code = forms.ChoiceField(choices=CURRENCY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    class Meta:
        model = GymOffice
        fields = ['currency_code', 'currency_symbol']
        widgets = {
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        currency_code = cleaned_data.get('currency_code')
        
        # Map symbols to codes
        symbol_map = {
            'INR': '₹',
            'USD': '$',
            'AED': 'AED',
            'EUR': '€',
            'GBP': '£',
            'SAR': 'SR',
            'QAR': 'QR',
            'KWD': 'KD',
            'BHD': 'BD',
            'OMR': 'RO',
        }
        
        if currency_code in symbol_map:
            cleaned_data['currency_symbol'] = symbol_map[currency_code]
        
        return cleaned_data

class GymBranchForm(forms.ModelForm):
    class Meta:
        model = GymBranch
        fields = ['name', 'address', 'email', 'phone', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class GymUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = CustomUser
        fields = ['email', 'phone_number', 'username', 'password', 'role', 'branch', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        gym = kwargs.pop('gym', None)
        super(GymUserForm, self).__init__(*args, **kwargs)
        
        # Limit roles to branch_admin, staff, trainer
        allowed_roles = [
            ('branch_admin', 'Branch Manager'),
            ('staff', 'Staff'),
            ('trainer', 'Trainer'),
        ]
        self.fields['role'].choices = allowed_roles
        
        # Filter branches to only those belonging to the gym
        if gym:
            self.fields['branch'].queryset = GymBranch.objects.filter(gym=gym, is_deleted=False)
            
        # Make branch optional by default (enforced by role in clean)
        self.fields['branch'].required = False
        
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        branch = cleaned_data.get('branch')
        
        if role == 'branch_admin' and not branch:
             self.add_error('branch', 'Branch Manager must be assigned to a specific branch.')
             
        return cleaned_data
        
    def save(self, commit=True):
        user = super(GymUserForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

class GymUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone_number', 'username', 'role', 'branch', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        gym = kwargs.pop('gym', None)
        super(GymUserEditForm, self).__init__(*args, **kwargs)
        
        # Limit roles to branch_admin, staff, trainer
        allowed_roles = [
            ('branch_admin', 'Branch Manager'),
            ('staff', 'Staff'),
            ('trainer', 'Trainer'),
        ]
        self.fields['role'].choices = allowed_roles
        
        # Filter branches to only those belonging to the gym
        if gym:
            self.fields['branch'].queryset = GymBranch.objects.filter(gym=gym, is_deleted=False)
            
        # Make branch optional by default (enforced by role in clean)
        self.fields['branch'].required = False
        
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        branch = cleaned_data.get('branch')
        
        if role == 'branch_admin' and not branch:
             self.add_error('branch', 'Branch Manager must be assigned to a specific branch.')
             
        return cleaned_data

from .models import LicenseKey

class LicenseKeyForm(forms.ModelForm):
    class Meta:
        model = LicenseKey
        fields = [
            'valid_until', 
            'fetcher_multi_branch', 'fetcher_food_log', 'fetcher_attendance', 'fetcher_payment',
            'max_branches', 'max_members', 'max_staff'
        ]
        widgets = {
            'valid_until': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fetcher_multi_branch': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fetcher_food_log': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fetcher_attendance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fetcher_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_branches': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_members': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_staff': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'max_branches': '0 = Unlimited',
            'max_members': '0 = Unlimited',
            'max_staff': '0 = Unlimited',
        }

class GymOfficeCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), required=True, label="Phone Number")

    class Meta:
        model = GymOffice
        fields = ['name', 'address', 'email', 'phone', 'logo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        email = cleaned_data.get("email")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
            
        return cleaned_data


from .models import HikConfigurationDb

class HikConfigurationForm(forms.ModelForm):
    class Meta:
        model = HikConfigurationDb
        fields = [
            'gym', 'gym_branch', 
            'middleware_url', 'middleware_port', 
            'device_ip', 'device_port', 
            'device_username', 'device_password'
        ]
        widgets = {
            'gym': forms.Select(attrs={'class': 'form-select'}),
            'gym_branch': forms.Select(attrs={'class': 'form-select'}),
            'middleware_url': forms.TextInput(attrs={'class': 'form-control'}),
            'middleware_port': forms.TextInput(attrs={'class': 'form-control'}),
            'device_ip': forms.TextInput(attrs={'class': 'form-control'}),
            'device_port': forms.TextInput(attrs={'class': 'form-control'}),
            'device_username': forms.TextInput(attrs={'class': 'form-control'}),
            'device_password': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}), 
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(HikConfigurationForm, self).__init__(*args, **kwargs)
        
        if user:
            # Logic for Branch Manager
            if user.role == 'branch_admin':
                 self.fields['gym'].widget = forms.HiddenInput()
                 self.fields['gym'].required = False
                 self.fields['gym'].initial = user.gym
                 
                 self.fields['gym_branch'].widget = forms.HiddenInput()
                 self.fields['gym_branch'].required = False
                 self.fields['gym_branch'].initial = user.branch
            
            # Logic for Gym Admin
            elif user.role == 'gym_admin':
                # Gym hidden as it is implied
                self.fields['gym'].widget = forms.HiddenInput()
                self.fields['gym'].required = False
                self.fields['gym'].initial = user.gym
                
                # Filter branches and set empty label for Main Office
                if user.gym:
                    self.fields['gym_branch'].queryset = GymBranch.objects.filter(gym=user.gym, is_deleted=False)
                
                self.fields['gym_branch'].empty_label = f"Main Office ({user.gym.name})"
                self.fields['gym_branch'].required = False

