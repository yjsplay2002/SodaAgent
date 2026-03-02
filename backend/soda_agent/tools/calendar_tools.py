from datetime import datetime, timedelta


def get_upcoming_events(hours_ahead: int = 24) -> dict:
    """Retrieves upcoming calendar events within the specified time window.

    Args:
        hours_ahead: Number of hours to look ahead. Default is 24.

    Returns:
        A dictionary with status and a list of upcoming events.
    """
    # MVP: Mock data. Production: Google Calendar API
    now = datetime.now()
    events = [
        {
            "title": "Team Standup",
            "start_time": (now + timedelta(hours=1)).strftime("%I:%M %p"),
            "end_time": (now + timedelta(hours=1, minutes=15)).strftime("%I:%M %p"),
            "location": "Google Meet",
        },
        {
            "title": "Dentist Appointment",
            "start_time": (now + timedelta(hours=3)).strftime("%I:%M %p"),
            "end_time": (now + timedelta(hours=4)).strftime("%I:%M %p"),
            "location": "123 Main St, San Francisco",
        },
    ]
    return {"status": "success", "events": events, "count": len(events)}


def create_event(title: str, date: str, time: str, duration_minutes: int = 60) -> dict:
    """Creates a new calendar event.

    Args:
        title: The title of the event.
        date: The date in YYYY-MM-DD format.
        time: The start time in HH:MM format (24-hour).
        duration_minutes: Duration in minutes. Default is 60.

    Returns:
        A dictionary confirming event creation.
    """
    return {
        "status": "success",
        "message": f"Event '{title}' created on {date} at {time} for {duration_minutes} minutes.",
    }


def get_free_slots(date: str) -> dict:
    """Gets available time slots for a given date.

    Args:
        date: The date to check in YYYY-MM-DD format.

    Returns:
        A dictionary with available time slots.
    """
    return {
        "status": "success",
        "date": date,
        "free_slots": [
            {"start": "09:00 AM", "end": "10:00 AM"},
            {"start": "11:30 AM", "end": "01:00 PM"},
            {"start": "03:00 PM", "end": "05:00 PM"},
        ],
    }
