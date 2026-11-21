from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from members.models import Member, Subscription
from notifications.models import Notification
from utils.whatsapp import send_member_expiry_whatsapp

class Command(BaseCommand):
    help = 'Send Meta WhatsApp subscription expiry reminders (default 5 days before ending day)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=5,
            help='Number of days before subscription end date to trigger reminder (default: 5)'
        )
        parser.add_argument(
            '--member-id',
            type=str,
            default=None,
            help='Optional specific member ID (e.g. GYM-00001 or primary key) to send reminder to'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sending even if a WhatsApp reminder was already sent today'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview which members would receive WhatsApp reminders without sending'
        )

    def handle(self, *args, **options):
        days = options['days']
        specific_member = options['member_id']
        force = options['force']
        dry_run = options['dry_run']

        today = timezone.now().date()
        target_date = today + timedelta(days=days)

        self.stdout.write(self.style.NOTICE(
            f"Scanning for active subscriptions expiring on {target_date} ({days} days from {today})..."
        ))

        subscriptions = Subscription.objects.filter(status='Active', end_date=target_date).select_related('member', 'member__gym')

        if specific_member:
            if specific_member.isdigit():
                subscriptions = subscriptions.filter(member__id=int(specific_member))
            else:
                subscriptions = subscriptions.filter(member__member_id__iexact=specific_member)

        total_count = subscriptions.count()
        self.stdout.write(f"Found {total_count} matching active subscription(s).")

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for sub in subscriptions:
            member = sub.member
            gym_name = member.gym.name if (member.gym and member.gym.name) else "PRO-FIT GYM"
            customer_name = member.first_name or member.full_name

            if dry_run:
                self.stdout.write(
                    f"  [DRY RUN] Would send to: {member.full_name} ({member.mobile_number}) | "
                    f"Expiry: {sub.end_date} | Gym: {gym_name}"
                )
                sent_count += 1
                continue

            if not force:
                already_sent = Notification.objects.filter(
                    member=member,
                    title="WhatsApp Expiry Reminder",
                    created_at__date=today
                ).exists()
                if already_sent:
                    self.stdout.write(f"  [SKIPPED] Already sent today to {member.full_name} ({member.member_id})")
                    skipped_count += 1
                    continue

            success, msg = send_member_expiry_whatsapp(member, subscription=sub, force=force)
            if success:
                self.stdout.write(self.style.SUCCESS(
                    f"  [SENT] {member.full_name} ({member.mobile_number}) -> Expiry: {sub.end_date}"
                ))
                sent_count += 1
            else:
                self.stdout.write(self.style.ERROR(
                    f"  [FAILED] {member.full_name} ({member.mobile_number}): {msg}"
                ))
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nCompleted: {sent_count} sent, {skipped_count} skipped, {failed_count} failed."
        ))
