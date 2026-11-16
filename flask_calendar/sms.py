"""Reminders sent as text messages (SMS), through Twilio.

The client turns this on in Settings > Reminders and enters her mobile number. The same
background check that sends notifications (see push.py) then also texts her each reminder.

The Twilio account details are secrets, so they come from environment variables on the
server (see config.py), never from the code.
"""
import logging
import re
from typing import Optional, Tuple

import requests
from flask import Flask

logger = logging.getLogger(__name__)


def configured(app: Flask) -> bool:
    """True when the server has a Twilio account to send texts with."""
    return all(app.config.get(name) for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"))


def normalize_phone(text: str) -> Optional[str]:
    """A phone number in international form (+16135551234), or None if it isn't one.

    10-digit numbers are taken as Canadian / US (+1)."""
    text = (text or "").strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def display_phone(number: str) -> str:
    """+16135551234 -> (613) 555-1234 for Canadian / US numbers."""
    if number and number.startswith("+1") and len(number) == 12:
        return "({}) {}-{}".format(number[2:5], number[5:8], number[8:])
    return number or ""


def text_for(message: dict) -> str:
    """Short, plain text (fits in one SMS) from a reminder message made by push.message_for."""
    body = message.get("body", "").replace(" · ", ", ")
    return "Energy Calendar reminder: {}. {}.".format(message.get("title", "Reminder"), body)


def send_text(app: Flask, to: str, body: str) -> Tuple[bool, str]:
    """Send one text. Returns (sent, error message)."""
    if not configured(app):
        return False, "Texting is not set up on the server yet."
    url = "{}/Accounts/{}/Messages.json".format(app.config["SMS_API_URL"].rstrip("/"), app.config["TWILIO_ACCOUNT_SID"])
    try:
        response = requests.post(
            url,
            data={"To": to, "From": app.config["TWILIO_FROM_NUMBER"], "Body": body},
            auth=(app.config["TWILIO_ACCOUNT_SID"], app.config["TWILIO_AUTH_TOKEN"]),
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning("Text message failed: %s", error)
        return False, "The text service could not be reached."
    if response.status_code >= 300:
        try:
            detail = response.json().get("message", "")
        except ValueError:
            detail = response.text[:200]
        logger.warning("Text message refused (%s): %s", response.status_code, detail)
        return False, detail or "The text service refused the message."
    return True, ""
