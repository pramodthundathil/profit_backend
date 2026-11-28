import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def send_notification_email(member, title, message):
    """Utility to send email to members"""
    recipient_email = getattr(member, 'email', None) or (getattr(member, 'user', None) and getattr(member.user, 'email', None))
    if not recipient_email:
        return False
    
    subject = f"PRO-FIT GYM: {title}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@profitgym.com')
    to_email = [recipient_email]
    
    # We can use a simple template later, for now plain text
    first_name = getattr(member, 'first_name', '')
    full_message = f"Hello {first_name},\n\n{message}\n\nBest regards,\nPRO-FIT GYM Team"
    
    try:
        send_mail(
            subject,
            full_message,
            from_email,
            to_email,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.exception("Error sending email to %s: %s", recipient_email, e)
        return False
