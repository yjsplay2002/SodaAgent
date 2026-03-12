"""Reminder / cron-job tools for the agent.

These tools let the agent schedule reminders that fire at a specific
time or after a delay.  When a reminder fires, the scheduler service
injects a prompt into the user's active Gemini Live session so the
agent can proactively speak to the user.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from services.live_tool_context import get_active_user_id
from services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)


def set_reminder(
    message: str,
    minutes_from_now: int | None = None,
    time: str | None = None,
) -> dict:
    """Sets a reminder that will proactively notify the user at the specified time.
    IMPORTANT: Call this tool ONLY ONCE per user request. If you already
    called set_reminder for this request, do NOT call it again.
    You must provide either minutes_from_now OR time, not both.

    Args:
        message: What to remind the user about. Be descriptive.
        minutes_from_now: Number of minutes from now to fire the reminder.
            Use this for relative times like '10분 뒤', 'in 5 minutes'.
        time: Absolute time in HH:MM (24-hour) format for today.
            Use this for specific times like '오후 3시' (15:00), '2pm' (14:00).

    Returns:
        A dictionary confirming the reminder was set.
    """
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user. Please try again."}

    now = datetime.now(timezone.utc)

    if minutes_from_now is not None:
        fire_at = now + timedelta(minutes=minutes_from_now)
    elif time is not None:
        try:
            # Parse HH:MM and set to today (in UTC for simplicity)
            hour, minute = map(int, time.split(":"))
            fire_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If the time has already passed today, set for tomorrow
            if fire_at <= now:
                fire_at += timedelta(days=1)
        except (ValueError, AttributeError):
            return {
                "status": "error",
                "message": f"Invalid time format: '{time}'. Use HH:MM (24-hour) format.",
            }
    else:
        return {
            "status": "error",
            "message": "Please specify either minutes_from_now or time.",
        }

    reminder = scheduler_service.add_reminder(
        user_id=user_id,
        message=message,
        fire_at=fire_at,
    )

    return {
        "status": "success",
        "message": (
            f"Reminder set: '{message}'. "
            f"I'll remind you in about {reminder.remaining_seconds // 60:.0f} minutes."
        ),
        "reminder_id": reminder.id,
        "fire_at": reminder.fire_at.isoformat(),
    }


def list_reminders() -> dict:
    """Lists all active reminders for the current user.

    Returns:
        A dictionary with the list of active reminders.
    """
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    reminders = scheduler_service.list_reminders(user_id)

    if not reminders:
        return {
            "status": "success",
            "message": "You have no active reminders.",
            "reminders": [],
        }

    return {
        "status": "success",
        "message": f"You have {len(reminders)} active reminder(s).",
        "reminders": reminders,
    }


def cancel_reminder(reminder_id: str) -> dict:
    """Cancels a single pending reminder by its ID.

    IMPORTANT: To cancel ALL reminders at once, use cancel_all_reminders instead.
    Do NOT call this tool multiple times in a loop.

    Args:
        reminder_id: The ID of the reminder to cancel.
    Returns:
        A dictionary confirming the cancellation.
    """
    success = scheduler_service.cancel_reminder(reminder_id)
    if success:
        return {
            "status": "success",
            "message": f"Reminder '{reminder_id}' has been cancelled.",
        }
    else:
        return {
            "status": "error",
            "message": f"Reminder '{reminder_id}' not found or already completed. Do NOT retry.",
        }


def cancel_all_reminders() -> dict:
    """Cancels ALL pending reminders for the current user at once.

    Use this when the user wants to cancel all their reminders.
    This is preferred over calling cancel_reminder multiple times.

    Returns:
        A dictionary confirming how many reminders were cancelled.
    """
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    count = scheduler_service.cancel_all_reminders(user_id)

    if count == 0:
        return {
            "status": "success",
            "message": "No active reminders to cancel.",
        }
    return {
        "status": "success",
        "message": f"Cancelled {count} reminder(s).",
    }