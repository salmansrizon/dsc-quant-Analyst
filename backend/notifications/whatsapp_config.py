"""
WhatsApp configuration (Twilio).
"""
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886") # Default Twilio sandbox number

WHATSAPP_ENABLED = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN])
