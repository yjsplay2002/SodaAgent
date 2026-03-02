"""Twilio PSTN outbound call management."""

import os

from twilio.rest import Client


class TwilioService:
    """Manages outbound PSTN calls via Twilio."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.backend_url = os.getenv("BACKEND_URL", "https://soda-agent.run.app")
        self.client = Client(self.account_sid, self.auth_token) if self.account_sid else None

    def initiate_call(self, to_number: str, trigger_context: str, call_id: str) -> dict:
        """Initiate an outbound call to the user.

        Args:
            to_number: User's phone number in E.164 format.
            trigger_context: Context message for why the agent is calling.
            call_id: Unique identifier for this call session.

        Returns:
            Dictionary with call SID and status.
        """
        if not self.client:
            return {"status": "error", "message": "Twilio not configured"}

        twiml = (
            f'<Response><Connect><Stream url="wss://{self.backend_url.replace("https://", "")}'
            f'/ws/twilio/{call_id}"/></Connect></Response>'
        )

        call = self.client.calls.create(
            to=to_number,
            from_=self.from_number,
            twiml=twiml,
        )

        return {
            "status": "success",
            "call_sid": call.sid,
            "to": to_number,
            "trigger_context": trigger_context,
        }
