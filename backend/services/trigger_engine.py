"""Proactive trigger evaluation engine."""

import uuid
from datetime import datetime, timedelta

from services.twilio_service import TwilioService


class TriggerEngine:
    """Evaluates triggers and initiates proactive outbound calls."""

    def __init__(self):
        self.twilio = TwilioService()

    def evaluate_triggers(self, user_id: str) -> list[dict]:
        """Evaluate all triggers for a user and fire any that match.

        Args:
            user_id: The user to evaluate triggers for.

        Returns:
            List of fired trigger results.
        """
        fired = []

        # Check calendar triggers
        calendar_trigger = self._check_calendar_trigger(user_id)
        if calendar_trigger:
            fired.append(calendar_trigger)

        return fired

    def _check_calendar_trigger(self, user_id: str) -> dict | None:
        """Check if any calendar events are coming up soon.

        MVP: Uses mock data. Production: Google Calendar API.
        """
        # Mock: Simulate an upcoming event
        upcoming_event = {
            "title": "Dentist Appointment",
            "start_time": datetime.now() + timedelta(minutes=15),
            "location": "123 Main St, San Francisco",
        }

        minutes_until = (upcoming_event["start_time"] - datetime.now()).total_seconds() / 60

        if 10 <= minutes_until <= 20:
            call_id = str(uuid.uuid4())
            context = (
                f"You have '{upcoming_event['title']}' in about {int(minutes_until)} minutes "
                f"at {upcoming_event['location']}. Would you like me to start navigation?"
            )

            # In production, get user's phone from Firestore
            # For now, return the trigger info without actually calling
            return {
                "type": "calendar_reminder",
                "event": upcoming_event["title"],
                "minutes_until": int(minutes_until),
                "context": context,
                "call_id": call_id,
            }

        return None

    def fire_trigger(self, user_phone: str, trigger: dict) -> dict:
        """Fire a trigger by initiating an outbound call.

        Args:
            user_phone: User's phone number in E.164 format.
            trigger: Trigger data from evaluate_triggers.

        Returns:
            Call result from Twilio.
        """
        return self.twilio.initiate_call(
            to_number=user_phone,
            trigger_context=trigger["context"],
            call_id=trigger["call_id"],
        )
