
import os
import django
import sys

# Setup Django environment
sys.path.append('d:\\GYM_UNIQUE\\profit_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'profit_backend.settings')
django.setup()

from members.models import Member
from home.models import CustomUser

print("--- FIXING MEMBERS ---")
members = Member.objects.filter(is_active=False)
for m in members:
    print(f"Re-activating Member: {m.full_name} ({m.member_id})")
    m.is_active = True
    m.save()
    
print("\n--- CURRENT MEMBERS ---")
all_members = Member.objects.all()
for m in all_members:
    print(f"ID: {m.id} | MemberID: {m.member_id} | Name: {m.full_name} | Active: {m.is_active}")
