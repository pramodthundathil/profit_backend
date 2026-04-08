from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_notification_email(member, title, message):
    """Utility to send email to members"""
    if not member.email:
        return False
    
    subject = f"PRO-FIT GYM: {title}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@profitgym.com')
    to_email = [member.email]
    
    # We can use a simple template later, for now plain text
    full_message = f"Hello {member.first_name},\n\n{message}\n\nBest regards,\nPRO-FIT GYM Team"
    
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
        print(f"Error sending email: {e}")
        return False
