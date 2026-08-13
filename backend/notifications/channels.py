"""Provider adapters for the non-email notification channels (#94).

`alert_checker.build_notifier` is the one caller — each function here mirrors
`email_sender.send_email`'s contract (bool: did the provider accept it) and its
missing-config behavior (return False rather than raise, so an unconfigured
channel just doesn't deliver instead of crashing the fan-out). A raised
exception is still possible (a network error from `requests.post` isn't caught
here) but that's fine: `alert_checker._deliver` already wraps the whole
notifier call in a try/except, same safety net `email_sender` relies on.

Providers chosen (#94 decision record):
- **Telegram**: the Bot API directly (`api.telegram.org`), no wrapper library.
  Needs `TELEGRAM_BOT_TOKEN` + the recipient's numeric `chat_id` (the user's
  `telegram_chat_id` notification pref, #78) — the user must have messaged the
  bot at least once for a chat_id to exist, same one-time step as this repo's
  own SDLC control channel (`docs/SDLC_LOOP.md`).
- **WhatsApp**: the Meta Cloud API (`graph.facebook.com`), not Twilio — no
  third-party billing relationship beyond a Meta Business/WhatsApp Business
  Platform account. Needs `WHATSAPP_API_TOKEN` (a permanent system-user access
  token, not a 24h test token) + `WHATSAPP_PHONE_NUMBER_ID` (the sending
  number's platform id, not the phone number itself) + the recipient's
  `whatsapp_number` pref.
"""
import logging
import os
import json
import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def send_telegram(chat_id: str, message: str) -> bool:
    if not TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    if resp.status_code != 200:
        logger.error("Telegram rejected a send to chat %s: %s %s",
                     chat_id, resp.status_code, resp.text[:200])
        return False
    return True


def send_whatsapp(phone_number: str, message: str) -> bool:
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return False
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    if resp.status_code != 200:
        logger.error("WhatsApp rejected a send to %s: %s %s",
                     phone_number, resp.status_code, resp.text[:200])
        return False
    return True


def send_web_push(subscription_json: str, payload: dict) -> bool:
    try:
        from pywebpush import webpush, WebPushException
        VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "")
        VAPID_EMAIL = os.environ.get("VAPID_EMAIL", "mailto:admin@example.com")
        if not VAPID_PRIVATE:
            return False
        subscription = json.loads(subscription_json)
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims={"sub": VAPID_EMAIL},
        )
        return True
    except Exception:
        return False
