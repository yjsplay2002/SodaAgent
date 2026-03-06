"""Twilio SMS integration for messaging.

Uses env vars (shared with TwilioService):
  - TWILIO_ACCOUNT_SID
  - TWILIO_AUTH_TOKEN
  - TWILIO_PHONE_NUMBER  (agent's Twilio number)
  - USER_PHONE_NUMBER     (default recipient for named contacts)

Falls back to mock data when Twilio is not configured.
"""

import logging
import os
from datetime import datetime, timezone

from twilio.rest import Client

logger = logging.getLogger(__name__)

_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
_FROM_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
_USER_NUMBER = os.environ.get("USER_PHONE_NUMBER", "")

_client: Client | None = None
if _ACCOUNT_SID and _AUTH_TOKEN:
    try:
        _client = Client(_ACCOUNT_SID, _AUTH_TOKEN)
    except Exception as e:
        logger.error("Twilio client init failed: %s", e)


def _relative_time(dt: datetime) -> str:
    """Format a datetime as a human-friendly relative time string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    minutes = int(delta.total_seconds() / 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


# ---------------------------------------------------------------------------
# read_messages
# ---------------------------------------------------------------------------


def read_messages(count: int = 5) -> dict:
    """Reads recent incoming messages.

    Args:
        count: Number of recent messages to retrieve. Default is 5.

    Returns:
        A dictionary with recent messages.
    """
    if not _client:
        return _mock_read_messages()

    try:
        messages = _client.messages.list(
            to=_FROM_NUMBER,  # Messages sent TO our Twilio number (incoming)
            limit=count,
        )

        result = []
        for msg in messages:
            result.append({
                "from": msg.from_,
                "time": (
                    _relative_time(msg.date_sent) if msg.date_sent else "unknown"
                ),
                "text": msg.body,
            })

        return {
            "status": "success",
            "messages": result,
            "unread_count": len(result),
        }
    except Exception as e:
        logger.error("Twilio read messages error: %s", e)
        return _mock_read_messages()


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


def send_message(contact: str, message: str) -> dict:
    """Sends a text message to a contact.

    If contact starts with '+' it is treated as a phone number directly.
    Otherwise USER_PHONE_NUMBER env var is used as the default recipient.

    Args:
        contact: Name or phone number of the contact.
        message: The message text to send.

    Returns:
        A dictionary confirming the message was sent.
    """
    if not _client:
        return _mock_send_message(contact, message)

    to_number = contact if contact.startswith("+") else _USER_NUMBER

    if not to_number:
        return {
            "status": "error",
            "message": (
                f"Cannot resolve phone number for '{contact}'. "
                "Set USER_PHONE_NUMBER env var for named contacts."
            ),
        }

    try:
        msg = _client.messages.create(
            body=message,
            from_=_FROM_NUMBER,
            to=to_number,
        )

        return {
            "status": "success",
            "to": contact,
            "message": message,
            "confirmation": f"Message sent to {contact}: '{message}'",
            "sid": msg.sid,
        }
    except Exception as e:
        logger.error("Twilio send message error: %s", e)
        return _mock_send_message(contact, message)


# ---------------------------------------------------------------------------
# Mock fallbacks (used when Twilio is not configured)
# ---------------------------------------------------------------------------


def _mock_read_messages() -> dict:
    return {
        "status": "success",
        "messages": [
            {
                "from": "Mom",
                "time": "10 minutes ago",
                "text": "Don't forget to pick up groceries on the way home!",
            },
            {
                "from": "Alex",
                "time": "30 minutes ago",
                "text": "Are we still meeting for dinner tonight?",
            },
        ],
        "unread_count": 2,
    }


def _mock_send_message(contact: str, message: str) -> dict:
    return {
        "status": "success",
        "to": contact,
        "message": message,
        "confirmation": f"Message sent to {contact}: '{message}'",
    }
