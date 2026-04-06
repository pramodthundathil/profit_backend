from django import forms
from .models import Payment
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
            
            # If user is branch manager, filter further
            if user.role == 'branch_admin' and user.branch:
                self.fields['member'].queryset = self.fields['member'].queryset.filter(branch=user.branch)
                self.fields['subscription'].queryset = self.fields['subscription'].queryset.filter(member__branch=user.branch)
                self.fields['installment'].queryset = self.fields['installment'].queryset.filter(subscription__member__branch=user.branch)

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
