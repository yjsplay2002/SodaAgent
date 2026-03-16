"""Twilio PSTN outbound call management."""

from __future__ import annotations

import html
import os

try:
    from twilio.rest import Client
except ModuleNotFoundError:
    Client = None


class TwilioService:
    """Manages outbound PSTN calls via Twilio."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.default_user_number = os.getenv("USER_PHONE_NUMBER")
        self.backend_url = os.getenv("BACKEND_URL", "https://soda-agent.run.app")
        self.client = (
            Client(self.account_sid, self.auth_token)
            if Client is not None and self.account_sid
            else None
        )

    def initiate_call(self, to_number: str | None, trigger_context: str, call_id: str) -> dict:
        """Initiate an outbound streaming call to the user."""
        resolved_number = self._resolve_to_number(to_number)
        if not resolved_number:
            return {
                "status": "error",
                "message": "No destination phone number configured.",
            }
        if not self.client or not self.from_number:
            return {
                "status": "error",
                "message": "Twilio not configured",
                "to": resolved_number,
            }

        twiml = (
            f'<Response><Connect><Stream url="wss://{self.backend_url.replace("https://", "")}'
            f'/ws/twilio/{call_id}"/></Connect></Response>'
        )

        call = self.client.calls.create(
            to=resolved_number,
            from_=self.from_number,
            twiml=twiml,
        )

        return {
            "status": "success",
            "call_sid": call.sid,
            "to": resolved_number,
            "trigger_context": trigger_context,
        }

    def initiate_message_call(
        self,
        to_number: str | None,
        message: str,
        *,
        call_id: str | None = None,
    ) -> dict:
        """Call the user and speak a short TTS message."""
        resolved_number = self._resolve_to_number(to_number)
        if not resolved_number:
            return {
                "status": "error",
                "message": "No destination phone number configured.",
            }
        if not self.client or not self.from_number:
            return {
                "status": "error",
                "message": "Twilio not configured",
                "to": resolved_number,
            }

        escaped_message = html.escape(message.strip(), quote=False)
        twiml = (
            "<Response>"
            '<Pause length="1"/>'
            f"<Say>{escaped_message}</Say>"
            "</Response>"
        )
        call = self.client.calls.create(
            to=resolved_number,
            from_=self.from_number,
            twiml=twiml,
        )
        return {
            "status": "success",
            "call_sid": call.sid,
            "call_id": call_id,
            "to": resolved_number,
            "message": message,
        }

    def _resolve_to_number(self, to_number: str | None) -> str | None:
        candidate = (to_number or self.default_user_number or "").strip()
        return candidate or None
