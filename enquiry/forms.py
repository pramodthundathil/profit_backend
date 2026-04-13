from django import forms
from .models import EnquiryData, EnquiryStatus

class EnquiryDataForm(forms.ModelForm):
    class Meta:
        model = EnquiryData
        fields = [
            'name', 'phone_number', 'email', 'age',
            'last_follow_up_date', 'next_follow_up_date',
            'status', 'conversion'
        ]
        widgets = {
            'last_follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'next_follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }

class EnquiryStatusForm(forms.ModelForm):
    class Meta:
        model = EnquiryStatus
        fields = ['description', 'status', 'call_status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class EnquiryFilterForm(forms.Form):
    search = forms.CharField(required=False, max_length=100)
    
    conversion = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('False', 'Pending'), ('True', 'Converted')]
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + EnquiryData.STATUS_CHOICES
    )
    
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
