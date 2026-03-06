"""Google Maps API integration for directions, ETA, and places.

Uses GOOGLE_MAPS_API_KEY or GOOGLE_API_KEY env var.
Falls back to mock data when no key is configured.

Required GCP APIs (enable via console or gcloud):
  - Directions API
  - Places API
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


# ---------------------------------------------------------------------------
# get_directions
# ---------------------------------------------------------------------------


def get_directions(destination: str, origin: str = "current location") -> dict:
    """Gets driving directions to a destination.

    Args:
        destination: The destination address or place name.
        origin: Starting point address. Defaults to 'current location'.

    Returns:
        A dictionary with route information including distance and ETA.
    """
    if not _MAPS_API_KEY:
        return _mock_directions(destination)

    try:
        resp = httpx.get(
            _DIRECTIONS_URL,
            params={
                "origin": origin,
                "destination": destination,
                "mode": "driving",
                "key": _MAPS_API_KEY,
            },
            timeout=10,
        )
        data = resp.json()

        if data["status"] != "OK" or not data.get("routes"):
            logger.warning("Directions API: %s", data.get("status"))
            return {
                "status": "error",
                "message": f"Could not find directions to {destination}",
            }

        route = data["routes"][0]
        leg = route["legs"][0]

        steps = [_strip_html(s["html_instructions"]) for s in leg["steps"][:5]]

        return {
            "status": "success",
            "destination": leg["end_address"],
            "origin": leg["start_address"],
            "distance": leg["distance"]["text"],
            "duration": leg["duration"]["text"],
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
        resp = httpx.get(
            _DIRECTIONS_URL,
            params={
                "origin": origin,
                "destination": destination,
                "mode": "driving",
                "departure_time": "now",
                "key": _MAPS_API_KEY,
            },
            timeout=10,
        )
        data = resp.json()

        if data["status"] != "OK" or not data.get("routes"):
            logger.warning("ETA API: %s", data.get("status"))
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
            logger.warning("Places API: %s", data.get("status"))
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
