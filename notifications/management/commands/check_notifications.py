from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from members.models import Member, Subscription, SubscriptionInstallment
from notifications.models import Notification
from utils.emails import send_notification_email

class Command(BaseCommand):
    help = 'Check for subscription expiries, overdue installments and sync member status'

    def handle(self, *args, **options):
        today = timezone.now().date()
        reminder_date = today + timedelta(days=3)

        self.stdout.write(self.style.SUCCESS(f'Running notification check for {today}...'))

        # 1. STATUS SYNC: Mark Expired Subscriptions
        # Subscriptions that passed their end_date but are still marked 'Active'
        expired_subs = Subscription.objects.filter(status='Active', end_date__lt=today)
        for sub in expired_subs:
            sub.status = 'Expired'
            sub.save(update_fields=['status'])
            self.stdout.write(f'Subscription {sub.id} of {sub.member.full_name} marked as Expired.')
            
            # Create notification
            Notification.objects.create(
                member=sub.member,
                title="Subscription Expired",
                message=f"Subscription for {sub.member.full_name} (ID: {sub.member.member_id}) has expired on {sub.end_date}.",
                notification_type='EXPIRY_REMINDER'
            )
            send_notification_email(sub.member, "Subscription Expired", f"Your subscription has expired on {sub.end_date}.")

        # 2. STATUS SYNC: Update Member status for all (ensure synchronization)
        for member in Member.objects.all():
            old_status = member.membership_status
            member.update_membership_status() # This method already exists in Member model
            if old_status != member.membership_status:
                 self.stdout.write(f'Member {member.full_name} status updated from {old_status} to {member.membership_status}.')

        # 3. EXPIRY REMINDERS: 3 days before expiry
        expiring_soon = Subscription.objects.filter(status='Active', end_date=reminder_date)
        for sub in expiring_soon:
            Notification.objects.create(
                member=sub.member,
                title="Subscription Expiring Soon",
                message=f"Subscription for {sub.member.full_name} (ID: {sub.member.member_id}) will expire in 3 days on {sub.end_date}.",
                notification_type='EXPIRY_REMINDER'
            )
            send_notification_email(sub.member, "Subscription Expiring Soon", f"Your subscription will expire in 3 days on {sub.end_date}.")

        # 4. OVERDUE INSTALLMENTS: Any installment due before today that is not paid
        overdue_installments = SubscriptionInstallment.objects.filter(
            due_date__lt=today
        ).exclude(status__in=['Paid', 'Overdue'])
        
        for inst in overdue_installments:
            inst.status = 'Overdue'
            inst.save(update_fields=['status'])
            
            Notification.objects.create(
                member=inst.subscription.member,
                title="Overdue Payment Alert",
                message=f"Installment #{inst.installment_number} of {inst.amount} for {inst.subscription.member.full_name} (ID: {inst.subscription.member.member_id}) was due on {inst.due_date} and is now overdue.",
                notification_type='OVERDUE_ALERT'
            )
            send_notification_email(
                inst.subscription.member, 
                "Overdue Payment Alert", 
                f"Your installment #{inst.installment_number} was due on {inst.due_date} and is now overdue."
            )

        self.stdout.write(self.style.SUCCESS('Notification check completed.'))
