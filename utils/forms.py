from django import forms
from .models import Batch_DB, TypeSubscription, SubscriptionPeriod

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch_DB
        exclude = ['gym']
        widgets = {
            'batch_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'batch_name': forms.Select(attrs={'class': 'form-control'}),
            'batch_status': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class TypeSubscriptionForm(forms.ModelForm):
    class Meta:
        model = TypeSubscription
        exclude = ['gym']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Zumba, CrossFit'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class SubscriptionPeriodForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPeriod
        exclude = ['gym']
        widgets = {
            'period': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of days'})
        }
