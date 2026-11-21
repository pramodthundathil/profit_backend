"""
WSGI config for profit_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'profit_backend.settings')

application = get_wsgi_application()
