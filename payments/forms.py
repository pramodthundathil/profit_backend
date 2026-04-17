from django import forms
from .models import Payment, GymOffer
from members.models import Member, Subscription, SubscriptionInstallment

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'member', 'subscription', 'installment', 
            'amount', 'payment_method', 'payment_date', 
            'transaction_id', 'notes', 'collected_by', 'status'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is provided, filter members and subscriptions by gym
        if user and user.gym:
            self.fields['member'].queryset = Member.objects.filter(gym=user.gym, is_active=True)
            self.fields['subscription'].queryset = Subscription.objects.filter(member__gym=user.gym)
            self.fields['installment'].queryset = SubscriptionInstallment.objects.filter(subscription__member__gym=user.gym)
            
            # Role-based filtering for branch staff
            if user.role in ['branch_admin', 'staff', 'trainer'] and user.branch:
                self.fields['member'].queryset = self.fields['member'].queryset.filter(branch=user.branch)
                self.fields['subscription'].queryset = self.fields['subscription'].queryset.filter(member__branch=user.branch)
                self.fields['installment'].queryset = self.fields['installment'].queryset.filter(subscription__member__branch=user.branch)

    def clean(self):
        cleaned_data = super().clean()
        subscription = cleaned_data.get('subscription')
        installment = cleaned_data.get('installment')

        if subscription and subscription.payment_terms == 'Installment':
            # Check if there are any installments for this subscription
            if subscription.installments.exists() and not installment:
                self.add_error('installment', "Selecting a specific installment is mandatory for this subscription's payment plan.")
        
        return cleaned_data

class PaymentFilterForm(forms.Form):
    search = forms.CharField(required=False, label="Search Name/ID")
    branch = forms.ChoiceField(required=False, label="Branch")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    status = forms.ChoiceField(
        required=False, 
        choices=(('', 'All Status'), ('Completed', 'Completed'), ('Pending', 'Pending'), ('Failed', 'Failed'))
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.gym:
            from home.models import GymBranch
            branches = [('', 'All Branches')] + [
                (str(b.id), b.name) for b in GymBranch.objects.filter(gym=user.gym, is_active=True, is_deleted=False)
            ]
            self.fields['branch'].choices = branches

class GymOfferForm(forms.ModelForm):
    class Meta:
        model = GymOffer
        fields = [
            'name', 'description', 'discount_percentage', 
            'start_date', 'end_date', 'is_active', 'specific_members'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'specific_members': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.gym:
            # Only show members from the same gym
            self.fields['specific_members'].queryset = Member.objects.filter(gym=user.gym, is_active=True)
