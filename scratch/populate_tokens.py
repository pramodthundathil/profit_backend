import os
import django
import uuid
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'profit_backend.settings')
django.setup()

from members.models import Member

def populate_tokens():
    members = Member.objects.filter(public_token__isnull=True)
    count = 0
    for member in members:
        member.public_token = uuid.uuid4()
        member.save(update_fields=['public_token'])
        count += 1
    print(f"Populated {count} member tokens.")

if __name__ == "__main__":
    populate_tokens()
