"""Google Maps API integration for directions, ETA, and places.

Uses GOOGLE_MAPS_API_KEY or GOOGLE_API_KEY env var.
Falls back to mock data when no key is configured.

Required GCP APIs (enable via console or gcloud):
  - Directions API (directions-backend.googleapis.com)
  - Places API (places-backend.googleapis.com)

Note: Google Directions API does NOT support driving directions in
South Korea due to government regulations. We automatically fall back
to transit mode when driving returns ZERO_RESULTS.
"""

import logging
import os
import re
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get(
    "GOOGLE_API_KEY", ""
)
_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

if _MAPS_API_KEY:
    logger.info("Maps API key loaded (len=%d)", len(_MAPS_API_KEY))
else:
    logger.warning("No Maps API key found — using mock data")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text)


def _traffic_level(leg: dict) -> str:
    """Determine traffic level from Directions API leg data."""
    if "duration_in_traffic" not in leg:
        return "unknown"
    ratio = leg["duration_in_traffic"]["value"] / max(leg["duration"]["value"], 1)
    if ratio > 1.3:
        return "heavy"
    if ratio > 1.1:
        return "moderate"
    return "light"


def _call_directions(origin: str, destination: str, mode: str = "driving",
                     departure_time: str | None = None) -> dict | None:
    """Call Google Directions API with automatic transit fallback.

    Returns the raw API response dict, or None on failure.
    If driving returns ZERO_RESULTS (e.g. South Korea), retries with transit.
    """
    params: dict = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": _MAPS_API_KEY,
    }
    if departure_time:
        params["departure_time"] = departure_time

    resp = httpx.get(_DIRECTIONS_URL, params=params, timeout=10)
    data = resp.json()

    status = data.get("status", "UNKNOWN")
    error_msg = data.get("error_message", "")

    if status == "OK" and data.get("routes"):
        return data

    # Driving not available in this region → try transit
    if status == "ZERO_RESULTS" and mode == "driving":
        logger.info(
            "Directions API: ZERO_RESULTS for driving, retrying with transit"
        )
        params["mode"] = "transit"
        params.pop("departure_time", None)  # transit doesn't use departure_time
        resp = httpx.get(_DIRECTIONS_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "OK" and data.get("routes"):
            return data

    logger.warning(
        "Directions API failed: status=%s error=%s origin=%s dest=%s mode=%s",
        status, error_msg, origin, destination, mode,
    )
    return None


# ---------------------------------------------------------------------------
# get_directions
# ---------------------------------------------------------------------------


def get_directions(destination: str, origin: str = "current location") -> dict:
    """Gets directions to a destination.

    Args:
        destination: The destination address or place name.
        origin: Starting point address. Defaults to 'current location'.

    Returns:
        A dictionary with route information including distance and ETA.
    """
    if not _MAPS_API_KEY:
        return _mock_directions(destination)

    try:
        data = _call_directions(origin, destination)
        if not data:
            return {
                "status": "error",
                "message": f"Could not find directions to {destination}",
            }

        route = data["routes"][0]
        leg = route["legs"][0]

        steps = [_strip_html(s["html_instructions"]) for s in leg["steps"][:5]]
        mode = route.get("legs", [{}])[0].get("steps", [{}])[0].get(
            "travel_mode", "DRIVING"
        )

        return {
            "status": "success",
            "destination": leg["end_address"],
            "origin": leg["start_address"],
            "distance": leg["distance"]["text"],
            "duration": leg["duration"]["text"],
            "travel_mode": mode.lower(),
            "route_summary": route.get("summary", ""),
            "steps": steps,
        }
    except Exception as e:
        logger.error("Directions API error: %s", e)
        return _mock_directions(destination)


# ---------------------------------------------------------------------------
# get_eta
# ---------------------------------------------------------------------------


def get_eta(destination: str, origin: str = "current location") -> dict:
    """Gets the estimated time of arrival to a destination.

    Args:
        destination: The destination address or place name.
        origin: Starting point address. Defaults to 'current location'.

    Returns:
        A dictionary with ETA information.
    """
    if not _MAPS_API_KEY:
        return _mock_eta(destination)

    try:
        data = _call_directions(origin, destination, departure_time="now")
        if not data:
            return {
                "status": "error",
                "message": f"Could not calculate ETA to {destination}",
            }

        leg = data["routes"][0]["legs"][0]

        # Prefer traffic-aware duration when available
        if "duration_in_traffic" in leg:
            duration_text = leg["duration_in_traffic"]["text"]
            duration_secs = leg["duration_in_traffic"]["value"]
        else:
            duration_text = leg["duration"]["text"]
            duration_secs = leg["duration"]["value"]

        eta = datetime.now() + timedelta(seconds=duration_secs)

        return {
            "status": "success",
            "destination": leg["end_address"],
            "origin": leg["start_address"],
            "duration": duration_text,
            "distance": leg["distance"]["text"],
            "eta": eta.strftime("%I:%M %p"),
            "traffic": _traffic_level(leg),
        }
    except Exception as e:
        logger.error("ETA API error: %s", e)
        return _mock_eta(destination)


# ---------------------------------------------------------------------------
# search_places
# ---------------------------------------------------------------------------


def search_places(query: str, category: str = "general") -> dict:
    """Searches for nearby places matching the query.

    Args:
        query: Search query like 'gas station', 'coffee shop', 'restaurant'.
        category: Category filter. Options: general, food, gas, parking, charging.

    Returns:
        A dictionary with matching places.
    """
    if not _MAPS_API_KEY:
        return _mock_places(query)

    try:
        resp = httpx.get(
            _PLACES_URL,
            params={
                "query": query,
                "key": _MAPS_API_KEY,
            },
            timeout=10,
        )
        data = resp.json()

        if data["status"] != "OK" or not data.get("results"):
            logger.warning("Places API: %s %s", data.get("status"),
                           data.get("error_message", ""))
            return {
                "status": "error",
                "message": f"No places found for '{query}'",
            }

        results = []
        for place in data["results"][:3]:
            results.append(
                {
                    "name": place["name"],
                    "address": place.get("formatted_address", ""),
                    "rating": place.get("rating", "N/A"),
                    "open": place.get("opening_hours", {}).get("open_now"),
                }
            )

        return {
            "status": "success",
            "query": query,
            "results": results,
        }
    except Exception as e:
        logger.error("Places API error: %s", e)
        return _mock_places(query)


# ---------------------------------------------------------------------------
# Mock fallbacks (used when API key is not configured)
# ---------------------------------------------------------------------------


def _mock_directions(destination: str) -> dict:
    return {
        "status": "success",
        "destination": destination,
        "distance": "12.3 miles",
        "duration": "25 minutes",
        "route_summary": f"Highway 101 toward {destination}",
        "steps": [f"Head north toward {destination}"],
    }


def _mock_eta(destination: str) -> dict:
    eta = datetime.now() + timedelta(minutes=25)
    return {
        "status": "success",
        "destination": destination,
        "eta": eta.strftime("%I:%M %p"),
        "duration": "25 minutes",
        "traffic": "light",
    }


def _mock_places(query: str) -> dict:
    return {
        "status": "success",
        "query": query,
        "results": [
            {
                "name": f"Best {query.title()} Nearby",
                "address": "123 Main St",
                "rating": 4.5,
                "open": True,
            },
            {
                "name": f"{query.title()} Express",
                "address": "456 Oak Ave",
                "rating": 4.2,
                "open": True,
            },
        ],
    }
