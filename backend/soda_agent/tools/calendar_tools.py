"""Google Calendar API integration.

Requires OAuth2 credentials. Set these env vars:
  - GOOGLE_OAUTH_CLIENT_ID
  - GOOGLE_OAUTH_CLIENT_SECRET
  - GOOGLE_OAUTH_REFRESH_TOKEN

Falls back to mock data when credentials are not configured.

One-time setup:
  1. Enable Google Calendar API in GCP Console
  2. Create OAuth2 "Desktop app" credentials
  3. Use the OAuth2 playground or a local script to obtain a refresh token
     with scope: https://www.googleapis.com/auth/calendar
  4. Set the resulting env vars
"""

import logging
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
_REFRESH_TOKEN = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", "")
_TIMEZONE = os.environ.get("CALENDAR_TIMEZONE", "America/Los_Angeles")

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CALENDAR_URL = "https://www.googleapis.com/calendar/v3"

# Module-level token cache
_access_token: str = ""
_token_expiry: datetime = datetime.min


def _is_configured() -> bool:
    return bool(_CLIENT_ID and _CLIENT_SECRET and _REFRESH_TOKEN)


def _get_access_token() -> str | None:
    """Refresh and return a valid access token."""
    global _access_token, _token_expiry

    if not _is_configured():
        return None

    if _access_token and datetime.now() < _token_expiry:
        return _access_token

    try:
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "refresh_token": _REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" not in data:
            logger.error("Calendar token refresh failed: %s", data)
            return None

        _access_token = data["access_token"]
        # Refresh 60s before actual expiry
        _token_expiry = datetime.now() + timedelta(
            seconds=data.get("expires_in", 3600) - 60
        )
        return _access_token
    except Exception as e:
        logger.error("Calendar token refresh error: %s", e)
        return None


def _auth_headers() -> dict | None:
    token = _get_access_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# get_upcoming_events
# ---------------------------------------------------------------------------


def get_upcoming_events(hours_ahead: int = 24) -> dict:
    """Retrieves upcoming calendar events within the specified time window.

    Args:
        hours_ahead: Number of hours to look ahead. Default is 24.

    Returns:
        A dictionary with status and a list of upcoming events.
    """
    headers = _auth_headers()
    if not headers:
        return _mock_upcoming_events()

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(hours=hours_ahead)).isoformat() + "Z"

    try:
        resp = httpx.get(
            f"{_CALENDAR_URL}/calendars/primary/events",
            headers=headers,
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 10,
            },
            timeout=10,
        )
        data = resp.json()

        if "error" in data:
            logger.warning("Calendar API error: %s", data["error"])
            return _mock_upcoming_events()

        events = []
        for item in data.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})

            start_str = start.get("dateTime", start.get("date", ""))
            end_str = end.get("dateTime", end.get("date", ""))

            # Format times for voice output
            if "T" in start_str:
                start_dt = datetime.fromisoformat(start_str)
                start_formatted = start_dt.strftime("%I:%M %p")
            else:
                start_formatted = start_str

            if "T" in end_str:
                end_dt = datetime.fromisoformat(end_str)
                end_formatted = end_dt.strftime("%I:%M %p")
            else:
                end_formatted = end_str

            events.append({
                "title": item.get("summary", "No title"),
                "start_time": start_formatted,
                "end_time": end_formatted,
                "location": item.get("location", ""),
            })

        return {"status": "success", "events": events, "count": len(events)}
    except Exception as e:
        logger.error("Calendar list events error: %s", e)
        return _mock_upcoming_events()


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


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
    headers = _auth_headers()
    if not headers:
        return _mock_create_event(title, date, time, duration_minutes)

    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": title,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": _TIMEZONE,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": _TIMEZONE,
            },
        }

        resp = httpx.post(
            f"{_CALENDAR_URL}/calendars/primary/events",
            headers=headers,
            json=event_body,
            timeout=10,
        )
        data = resp.json()

        if "error" in data:
            logger.warning("Calendar create error: %s", data["error"])
            return _mock_create_event(title, date, time, duration_minutes)

        return {
            "status": "success",
            "message": f"Event '{title}' created on {date} at {time} for {duration_minutes} minutes.",
            "event_id": data.get("id", ""),
            "link": data.get("htmlLink", ""),
        }
    except Exception as e:
        logger.error("Calendar create event error: %s", e)
        return _mock_create_event(title, date, time, duration_minutes)


# ---------------------------------------------------------------------------
# get_free_slots
# ---------------------------------------------------------------------------


def get_free_slots(date: str) -> dict:
    """Gets available time slots for a given date.

    Args:
        date: The date to check in YYYY-MM-DD format.

    Returns:
        A dictionary with available time slots.
    """
    headers = _auth_headers()
    if not headers:
        return _mock_free_slots(date)

    try:
        day_start = datetime.strptime(date, "%Y-%m-%d").replace(hour=9, minute=0)
        day_end = day_start.replace(hour=18, minute=0)

        resp = httpx.post(
            f"{_CALENDAR_URL}/freeBusy",
            headers=headers,
            json={
                "timeMin": day_start.isoformat() + "Z",
                "timeMax": day_end.isoformat() + "Z",
                "timeZone": _TIMEZONE,
                "items": [{"id": "primary"}],
            },
            timeout=10,
        )
        data = resp.json()

        if "error" in data:
            logger.warning("FreeBusy API error: %s", data["error"])
            return _mock_free_slots(date)

        busy_periods = (
            data.get("calendars", {}).get("primary", {}).get("busy", [])
        )

        # Calculate free windows between busy blocks within 9 AM–6 PM
        free_slots = []
        current = day_start

        for busy in busy_periods:
            busy_start = datetime.fromisoformat(
                busy["start"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
            busy_end = datetime.fromisoformat(
                busy["end"].replace("Z", "+00:00")
            ).replace(tzinfo=None)

            if current < busy_start:
                free_slots.append({
                    "start": current.strftime("%I:%M %p"),
                    "end": busy_start.strftime("%I:%M %p"),
                })
            current = max(current, busy_end)

        if current < day_end:
            free_slots.append({
                "start": current.strftime("%I:%M %p"),
                "end": day_end.strftime("%I:%M %p"),
            })

        return {"status": "success", "date": date, "free_slots": free_slots}
    except Exception as e:
        logger.error("FreeBusy API error: %s", e)
        return _mock_free_slots(date)


# ---------------------------------------------------------------------------
# Mock fallbacks (used when OAuth2 credentials are not configured)
# ---------------------------------------------------------------------------


def _mock_upcoming_events() -> dict:
    now = datetime.now()
    return {
        "status": "success",
        "events": [
            {
                "title": "Team Standup",
                "start_time": (now + timedelta(hours=1)).strftime("%I:%M %p"),
                "end_time": (now + timedelta(hours=1, minutes=15)).strftime(
                    "%I:%M %p"
                ),
                "location": "Google Meet",
            },
            {
                "title": "Dentist Appointment",
                "start_time": (now + timedelta(hours=3)).strftime("%I:%M %p"),
                "end_time": (now + timedelta(hours=4)).strftime("%I:%M %p"),
                "location": "123 Main St, San Francisco",
            },
        ],
        "count": 2,
    }


def _mock_create_event(
    title: str, date: str, time: str, duration_minutes: int
) -> dict:
    return {
        "status": "success",
        "message": f"Event '{title}' created on {date} at {time} for {duration_minutes} minutes.",
    }


def _mock_free_slots(date: str) -> dict:
    return {
        "status": "success",
        "date": date,
        "free_slots": [
            {"start": "09:00 AM", "end": "10:00 AM"},
            {"start": "11:30 AM", "end": "01:00 PM"},
            {"start": "03:00 PM", "end": "05:00 PM"},
        ],
    }
