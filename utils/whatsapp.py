import re
import json
import logging
from datetime import datetime, date
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('whatsapp')

def format_phone_number(phone: str) -> str:
    """
    Format recipient phone number:
    - Strips all non-digit characters.
    - If 10 digits (standard Indian number without country code), prepends 91.
    """
    cleaned = re.sub(r"[^0-9]", "", str(phone or ""))
    if len(cleaned) == 10:
        cleaned = "91" + cleaned
    return cleaned


def send_whatsapp_template(
    recipient: str,
    customer_name: str,
    expiry_date: str,
    gym_name: str
):
    """
    Send an approved Meta WhatsApp Cloud API template message.
    
    Template Parameters:
      {{1}} -> customer_name
      {{2}} -> expiry_date
      {{3}} -> gym_name
      
    Returns:
      (success: bool, message: str, data: dict or None)
    """
    phone_number_id = getattr(settings, 'META_WHATSAPP_PHONE_NUMBER_ID', None)
    access_token = getattr(settings, 'META_WHATSAPP_ACCESS_TOKEN', None)
    template_name = getattr(settings, 'META_WHATSAPP_TEMPLATE_NAME', 'subscription_end')
    template_lang = getattr(settings, 'META_WHATSAPP_TEMPLATE_LANG', 'en')
    api_version = getattr(settings, 'META_WHATSAPP_GRAPH_API_VERSION', 'v21.0')

    if not phone_number_id:
        return False, "Meta WhatsApp PHONE_NUMBER_ID is not configured.", None

    if not access_token:
        return False, "Meta WhatsApp ACCESS_TOKEN is not configured.", None

    formatted_recipient = format_phone_number(recipient)
    if not formatted_recipient or len(formatted_recipient) < 10:
        return False, f"Invalid recipient phone number: '{recipient}'.", None

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": formatted_recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": template_lang
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(customer_name)},
                        {"type": "text", "text": str(expiry_date)},
                        {"type": "text", "text": str(gym_name)}
                    ]
                }
            ]
        }
    }

    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logger.info(
        f"Sending WhatsApp message to +{formatted_recipient} using template '{template_name}' "
        f"[customer_name: '{customer_name}', expiry_date: '{expiry_date}', gym_name: '{gym_name}']"
    )

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response_data = response.json() if response.content else {}

        if response.status_code in (200, 201):
            logger.info(f"WhatsApp message sent successfully: {response_data}")
            return True, "WhatsApp message sent successfully.", response_data
        else:
            err_msg = "Unknown Meta API error"
            if isinstance(response_data, dict) and "error" in response_data:
                err_info = response_data["error"]
                err_msg = err_info.get("message", str(err_info))
            else:
                err_msg = response.text or f"HTTP {response.status_code}"
            logger.error(f"Meta API error (Status {response.status_code}): {err_msg}")
            return False, f"Meta API Error ({response.status_code}): {err_msg}", response_data

    except requests.RequestException as e:
        logger.error(f"Network error connecting to Meta WhatsApp API: {e}")
        return False, f"Network error sending WhatsApp: {str(e)}", None
    except Exception as e:
        logger.error(f"Unexpected error in send_whatsapp_template: {e}")
        return False, f"Unexpected error: {str(e)}", None


def send_member_expiry_whatsapp(member, subscription=None, force=False):
    """
    High-level helper to send a subscription expiry reminder to a Member via WhatsApp.
    
    Resolves:
      - recipient: member.mobile_number
      - customer_name: member.first_name or member.full_name
      - expiry_date: subscription.end_date or member.access_expiry_date (formatted as DD/MM/YYYY)
      - gym_name: member.gym.name (using {{3}} in gym name)
      
    Creates an in-app Notification upon success.
    
    Returns:
      (success: bool, message: str)
    """
    if not member.mobile_number:
        return False, f"Member {member.full_name} has no mobile number."

    target_date = None
    if subscription and subscription.end_date:
        target_date = subscription.end_date
    elif member.access_expiry_date:
        target_date = member.access_expiry_date
    elif member.current_subscription and member.current_subscription.end_date:
        target_date = member.current_subscription.end_date
    else:
        # Check active subscriptions
        active_sub = member.subscriptions.filter(status='Active').order_by('-end_date').first()
        if active_sub and active_sub.end_date:
            target_date = active_sub.end_date
        else:
            # Fallback to latest non-cancelled subscription
            latest_sub = member.subscriptions.exclude(status='Cancelled').order_by('-end_date').first()
            if latest_sub and latest_sub.end_date:
                target_date = latest_sub.end_date

    if not target_date:
        return False, f"Member {member.full_name} has no active or upcoming subscription with an expiry date."

    if isinstance(target_date, (datetime, date)):
        formatted_expiry = target_date.strftime("%d/%m/%Y")
    else:
        formatted_expiry = str(target_date)

    customer_name = (member.first_name or member.full_name or "Member").strip()
    gym_name = (member.gym.name if (member.gym and member.gym.name) else "PRO-FIT GYM").strip()

    success, msg, _ = send_whatsapp_template(
        recipient=member.mobile_number,
        customer_name=customer_name,
        expiry_date=formatted_expiry,
        gym_name=gym_name
    )

    if success:
        try:
            from notifications.models import Notification
            Notification.objects.create(
                member=member,
                title="WhatsApp Expiry Reminder",
                message=(
                    f"WhatsApp expiry reminder sent to {member.mobile_number} "
                    f"for subscription expiring on {formatted_expiry} (Gym: {gym_name})."
                ),
                notification_type='EXPIRY_REMINDER'
            )
        except Exception as e:
            logger.warning(f"Could not record Notification in database: {e}")

        return True, f"WhatsApp expiry reminder sent to {member.full_name} ({member.mobile_number})."
    else:
        return False, msg
