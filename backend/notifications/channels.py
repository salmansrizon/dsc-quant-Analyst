import os
import json
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def send_telegram(chat_id: str, message: str) -> bool:
    if not TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    return resp.status_code == 200


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
    return resp.status_code == 200


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
