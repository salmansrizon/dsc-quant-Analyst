"""
Service to send WhatsApp messages via Twilio.
"""
from .whatsapp_config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, WHATSAPP_ENABLED
import requests

def send_whatsapp_message(to_number, text):
    """Sends a WhatsApp message via Twilio API."""
    if not WHATSAPP_ENABLED:
        print("WhatsApp notifications not configured.")
        return False
        
    url = f"https://api.twilio.org/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:{to_number}",
        "Body": text
    }
    
    try:
        response = requests.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return False
