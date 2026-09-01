import sqlite3
import os
import argparse
from datetime import datetime, date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from home.models import GymOffice
from utils.models import Batch_DB, TypeSubscription
from members.models import Member, Subscription
from payments.models import Payment
from finance.models import FinanceTransaction

class Command(BaseCommand):
    help = 'Migrates data from legacy SQLite database to profit_backend for a specific GymOffice'

    def add_arguments(self, parser):
        parser.add_argument('--legacy-db', type=str, required=True, help='Path to legacy SQLite DB')
        parser.add_argument('--gym-id', type=int, required=True, help='Target GymOffice ID')
        parser.add_argument('--dry-run', action='store_true', help='Do not commit changes')

    def handle(self, *args, **options):
        legacy_db_path = options['legacy_db']
        gym_id = options['gym_id']
        dry_run = options['dry_run']

        if not os.path.exists(legacy_db_path):
            self.stdout.write(self.style.ERROR(f"Database file not found: {legacy_db_path}"))
            return

        try:
            gym = GymOffice.objects.get(id=gym_id)
        except GymOffice.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"GymOffice with id {gym_id} does not exist."))
            return

        conn = sqlite3.connect(legacy_db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        self.stdout.write(f"Starting migration to GymOffice: {gym.name} (Dry run: {dry_run})")

        # 1. Batches
        self.stdout.write("Migrating Batches...")
        cur.execute("SELECT * FROM Members_batch_db")
        legacy_batches = cur.fetchall()
        batch_map = {} # old_id -> new_instance
        for row in legacy_batches:
            old_id = row['id']
            # Map choice: Morning, Evening, Night
            name = row['Batch_Name']
            if name not in ['Morning', 'Evening', 'Night']:
                name = 'Morning' # Default fallback if weird name
            
            if not dry_run:
                batch, created = Batch_DB.objects.get_or_create(
                    gym=gym,
                    batch_name=name,
                    batch_time=row['Batch_Time'],
                    defaults={'batch_status': bool(row['Batch_Status'])}
                )
                batch_map[old_id] = batch

        # 2. Subscription Types
        self.stdout.write("Migrating Subscription Types...")
        cur.execute("SELECT * FROM Members_typesubsription")
        legacy_types = cur.fetchall()
        type_map = {}
        for row in legacy_types:
            old_id = row['id']
            if not dry_run:
                stype, created = TypeSubscription.objects.get_or_create(
                    gym=gym,
                    name=row['Type'],
                    defaults={'is_active': True}
                )
                type_map[old_id] = stype

        # 3. Subscription Periods (cache for lookup)
        cur.execute("SELECT * FROM Members_subscription_period")
        legacy_periods = cur.fetchall()
        period_map = {} # old_id -> {'duration': int, 'unit': str}
        for row in legacy_periods:
            # Map category to new unit
            cat = row['Category']
            if cat == 'Day': unit = 'Days'
            elif cat == 'Week': unit = 'Weeks'
            elif cat == 'Month': unit = 'Months'
            elif cat == 'Year': unit = 'Years'
            else: unit = 'Months'
            period_map[row['id']] = {'duration': row['Period'], 'unit': unit}

        # 4. Members
        self.stdout.write("Migrating Members...")
        cur.execute("SELECT * FROM Members_memberdata")
        legacy_members = cur.fetchall()
        member_map = {} # old_id -> new_instance
        for row in legacy_members:
            old_id = row['id']
            mobile = row['Mobile_Number'] or '0000000000'
            
            if not dry_run:
                # Handle unique constraint
                base_mobile = mobile
                suffix = 1
                while Member.all_objects.filter(gym=gym, mobile_number=mobile).exists():
                    mobile = f"{base_mobile}-{suffix}"
                    suffix += 1

                # Parse dates
                dob = row['Date_Of_Birth']
                reg_date = row['Registration_Date'] or date.today()
                
                # Check height weight valid decimal
                height = None
                if row['Height']:
                    try: height = Decimal(row['Height'])
                    except: pass
                weight = None
                if row['Weight']:
                    try: weight = Decimal(row['Weight'])
                    except: pass
                
                access_token = row['Access_Token_Id']
                if access_token:
                    base_token = access_token
                    token_suffix = 1
                    while Member.all_objects.filter(access_token=access_token).exists():
                        access_token = f"{base_token}-{token_suffix}"
                        token_suffix += 1

                # We won't copy files directly yet, just create text
                member = Member.objects.create(
                    gym=gym,
                    first_name=row['First_Name'] or 'Unknown',
                    last_name=row['Last_Name'] or '',
                    date_of_birth=dob,
                    gender=row['Gender'] if row['Gender'] in ['Male', 'Female', 'Other'] else 'Other',
                    mobile_number=mobile,
                    email=row['Email'],
                    address=row['Address'],
                    height=height,
                    weight=weight,
                    medical_history=row['Medical_History'],
                    registration_date=reg_date,
                    is_active=bool(row['Active_status']),
                    access_enabled=bool(row['Access_status']),
                    access_token=access_token
                )
                member_map[old_id] = member

        # 5. Subscriptions
        self.stdout.write("Migrating Subscriptions...")
        cur.execute("SELECT * FROM Members_subscription")
        legacy_subs = cur.fetchall()
        sub_map = {}
        for row in legacy_subs:
            old_id = row['id']
            member_old_id = row['Member_id']
            if not member_old_id or member_old_id not in member_map:
                continue

            # Period info
            p_info = period_map.get(row['Period_Of_Subscription_id'], {'duration': 1, 'unit': 'Months'})
            
            if not dry_run:
                # Parse dates
                start_str = row['Subscribed_Date']
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str and isinstance(start_str, str) else start_str
                if not start_date:
                    start_date = date.today()

                end_str = row['Subscription_End_Date']
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str and isinstance(end_str, str) else end_str

                sub = Subscription(
                    member=member_map[member_old_id],
                    subscription_type=type_map.get(row['Type_Of_Subscription_id']),
                    batch=batch_map.get(row['Batch_id']),
                    duration=p_info['duration'],
                    duration_unit=p_info['unit'],
                    start_date=start_date,
                    end_date=end_date,
                    base_amount=Decimal(str(row['Amount'] or 0)),
                    final_amount=Decimal(str(row['Amount'] or 0)),
                    payment_terms='Full',
                    status='Active' if row['Payment_Status'] else 'Suspended'
                )
                sub.save() # This triggers auto-amount rules etc
                sub_map[old_id] = sub

        # 6. Payments
        self.stdout.write("Migrating Payments...")
        cur.execute("SELECT * FROM Members_payment")
        legacy_payments = cur.fetchall()
        for row in legacy_payments:
            sub_old_id = row['Subscription_ID_id']
            member_old_id = row['Member_id']
            if not sub_old_id or sub_old_id not in sub_map:
                continue
            if not member_old_id or member_old_id not in member_map:
                continue
                
            amount = row['Amount'] or 0
            if amount <= 0:
                continue

            # Map mode
            mode = row['Mode_of_Payment']
            if mode not in ['Cash', 'Card', 'Bank Transfer', 'UPI', 'Cheque', 'Online', 'Tabby']:
                mode = 'Cash' # default fallback
                
            if not dry_run:
                Payment.objects.create(
                    subscription=sub_map[sub_old_id],
                    member=member_map[member_old_id],
                    amount=Decimal(str(amount)),
                    payment_method=mode,
                    payment_date=row['Payment_Date'] or date.today(),
                    status='Completed' if row['Payment_Status'] else 'Pending'
                )

        # 7. Finance Transactions (Income & Expence)
        self.stdout.write("Migrating Finance...")
        try:
            cur.execute("SELECT * FROM Finance_income")
            legacy_income = cur.fetchall()
            for row in legacy_income:
                if not dry_run:
                    FinanceTransaction.objects.create(
                        gym=gym,
                        transaction_type='Income',
                        amount=Decimal(str(row['amount'] or 0)),
                        date=row['date'],
                        description=row['perticulers'] or 'Income',
                        category=row['other']
                    )
        except sqlite3.OperationalError:
            self.stdout.write("Finance_income table not found or error reading.")
            
        try:
            cur.execute("SELECT * FROM Finance_expence")
            legacy_expense = cur.fetchall()
            for row in legacy_expense:
                if not dry_run:
                    FinanceTransaction.objects.create(
                        gym=gym,
                        transaction_type='Expense',
                        amount=Decimal(str(row['amount'] or 0)),
                        date=row['date'],
                        description=row['perticulers'] or 'Expense',
                        category=row['other']
                    )
        except sqlite3.OperationalError:
            self.stdout.write("Finance_expence table not found or error reading.")

        conn.close()
        self.stdout.write(self.style.SUCCESS("Migration completed successfully!"))
