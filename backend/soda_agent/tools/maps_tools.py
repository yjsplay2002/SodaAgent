"""Map provider integration for directions, ETA, and places.

Primary behavior:
  - South Korea routes: NAVER Maps Directions 5
  - Other routes: Google Maps Directions / Places

Google Maps remains the fallback for non-Korean routing and place search.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

import httpx
from services.live_tool_context import get_current_session_location

logger = logging.getLogger(__name__)

_MAPS_API_KEY = (
    os.environ.get("GOOGLE_MAPS_API_KEY")
    or os.environ.get("GOOGLE_API_KEY", "")
).strip()
_NAVER_MAPS_API_KEY_ID = os.environ.get("NAVER_MAPS_API_KEY_ID", "").strip()
_NAVER_MAPS_API_KEY = os.environ.get("NAVER_MAPS_API_KEY", "").strip()
_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_NAVER_DIRECTIONS_URL = "https://maps.apigw.ntruss.com/map-direction/v1/driving"
_NAVER_GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"

if _MAPS_API_KEY:
    logger.info("Maps API key loaded (len=%d)", len(_MAPS_API_KEY))
else:
    logger.warning("No Maps API key found")

if _NAVER_MAPS_API_KEY_ID and _NAVER_MAPS_API_KEY:
    logger.info(
        "NAVER Maps credentials loaded (id_len=%d key_len=%d)",
        len(_NAVER_MAPS_API_KEY_ID),
        len(_NAVER_MAPS_API_KEY),
    )
else:
    logger.info("NAVER Maps credentials not configured")


_TRAVEL_TIME_KO_RE = re.compile(
    r"^\s*(?P<origin>.+?)에서\s+(?P<destination>.+?)까지"
)
_TRAVEL_TIME_EN_RE = re.compile(
    r"\bfrom\s+(?P<origin>.+?)\s+to\s+(?P<destination>.+?)(?:\s+(?:take|takes|is|would|will)\b|[?.!,]|$)",
    re.IGNORECASE,
)
_DESTINATION_ONLY_KO_RE = re.compile(
    r"^\s*(?P<destination>.+?)까지\s+(?:얼마나|몇)\s*(?:걸려|걸리|걸릴까)"
)
_DESTINATION_ONLY_EN_RE = re.compile(
    r"\b(?:to|for)\s+(?P<destination>.+?)(?:\s+(?:how long|eta|travel time)\b|[?.!,]|$)",
    re.IGNORECASE,
)
_TRAILING_QUERY_NOISE_RE = re.compile(
    r"\s*(?:얼마나|몇)\s*(?:걸려|걸리|걸릴까).*$|\s*(?:how long|eta|travel time).*$",
    re.IGNORECASE,
)
_PLACE_SUFFIX_NOISE_RE = re.compile(
    r"\s*(?:까지|가는\s*길|가는길|걸리는\s*시간|소요\s*시간|travel\s*time|eta)\s*$",
    re.IGNORECASE,
)
_COORDINATE_PAIR_RE = re.compile(
    r"^\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)\s*$"
)
_COORDINATE_SENTENCE_RE = re.compile(
    r"latitude\s*(?P<lat>-?\d+(?:\.\d+)?)\D+longitude\s*(?P<lon>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_COORDINATE_LABEL_RE = re.compile(
    r"coordinates?\s*[:=]\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_HANGUL_RE = re.compile(r"[가-힣]")
_KOREA_LAT_RANGE = (32.0, 39.5)
_KOREA_LON_RANGE = (123.0, 132.5)
_KOREA_PLACE_KEYWORDS = {
    "대한민국",
    "한국",
    "남한",
    "서울",
    "부산",
    "인천",
    "대구",
    "대전",
    "광주",
    "울산",
    "세종",
    "제주",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "seoul",
    "busan",
    "incheon",
    "daegu",
    "daejeon",
    "gwangju",
    "ulsan",
    "sejong",
    "jeju",
    "gyeonggi",
    "gangwon",
    "chungbuk",
    "chungnam",
    "jeonbuk",
    "jeonnam",
    "gyeongbuk",
    "gyeongnam",
    "south korea",
    "republic of korea",
    "korea",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text)


def _format_distance_meters(distance_meters: int | float) -> str:
    if distance_meters >= 1000:
        return f"{distance_meters / 1000:.1f} km"
    return f"{int(distance_meters)} m"


def _format_duration_seconds(duration_seconds: int | float) -> str:
    total_minutes = max(1, round(duration_seconds / 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} hr {minutes} min"
    if hours:
        return f"{hours} hr"
    return f"{minutes} min"


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


def _clean_place_text(text: str) -> str:
    """Normalize a place fragment extracted from a natural-language query."""
    cleaned = text.strip().strip("?.!,")
    cleaned = _TRAILING_QUERY_NOISE_RE.sub("", cleaned).strip()
    cleaned = _PLACE_SUFFIX_NOISE_RE.sub("", cleaned).strip()
    return cleaned.strip("?.!,")


def _uses_current_location(value: str | None) -> bool:
    if value is None:
        return True

    normalized = " ".join(value.strip().lower().split())
    return normalized in {
        "",
        "current location",
        "my location",
        "here",
        "current",
        "현재 위치",
        "지금 위치",
        "내 위치",
        "현위치",
    }


def _normalize_place_input(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        return value

    normalized = _clean_place_text(normalized)

    for pattern in (
        _COORDINATE_PAIR_RE,
        _COORDINATE_SENTENCE_RE,
        _COORDINATE_LABEL_RE,
    ):
        match = pattern.search(normalized)
        if not match:
            continue

        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return f"{lat:.5f},{lon:.5f}"

    return normalized


def _extract_coordinates(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None

    text = " ".join(value.strip().split())
    for pattern in (
        _COORDINATE_PAIR_RE,
        _COORDINATE_SENTENCE_RE,
        _COORDINATE_LABEL_RE,
    ):
        match = pattern.search(text)
        if not match:
            continue

        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon

    return None


def _is_korea_coordinate(lat: float, lon: float) -> bool:
    return (
        _KOREA_LAT_RANGE[0] <= lat <= _KOREA_LAT_RANGE[1]
        and _KOREA_LON_RANGE[0] <= lon <= _KOREA_LON_RANGE[1]
    )


def _has_naver_credentials() -> bool:
    return bool(_NAVER_MAPS_API_KEY_ID and _NAVER_MAPS_API_KEY)


def _naver_headers() -> dict[str, str]:
    return {
        "x-ncp-apigw-api-key-id": _NAVER_MAPS_API_KEY_ID,
        "x-ncp-apigw-api-key": _NAVER_MAPS_API_KEY,
    }


def _resolve_origin_input(origin: str | None) -> str:
    if _uses_current_location(origin):
        location = get_current_session_location()
        if location:
            lat, lon = location
            return f"{lat:.5f},{lon:.5f}"
        return "current location"

    return _normalize_place_input(origin or "current location")


def _looks_like_korean_place(value: str | None) -> bool:
    if _uses_current_location(value):
        location = get_current_session_location()
        return bool(location and _is_korea_coordinate(location[0], location[1]))

    normalized = _normalize_place_input(value or "")
    coordinates = _extract_coordinates(normalized)
    if coordinates:
        return _is_korea_coordinate(coordinates[0], coordinates[1])

    lowered = normalized.lower()
    if _HANGUL_RE.search(normalized):
        return True

    return any(keyword in lowered for keyword in _KOREA_PLACE_KEYWORDS)


def _resolve_route_endpoints(
    destination: str,
    origin: str,
) -> tuple[str, str]:
    # Recover from model calls that accidentally reverse origin/destination.
    if _uses_current_location(destination) and not _uses_current_location(origin):
        return origin, _resolve_origin_input(destination)
    return destination, origin


def _extract_route_from_query(query: str) -> tuple[str | None, str | None]:
    """Best-effort extraction of origin/destination from a travel-time question."""
    normalized = " ".join(query.strip().split())
    if not normalized:
        return None, None

    for pattern in (_TRAVEL_TIME_KO_RE, _TRAVEL_TIME_EN_RE):
        match = pattern.search(normalized)
        if match:
            origin = _clean_place_text(match.group("origin"))
            destination = _clean_place_text(match.group("destination"))
            if origin and destination:
                return origin, destination

    for pattern in (_DESTINATION_ONLY_KO_RE, _DESTINATION_ONLY_EN_RE):
        match = pattern.search(normalized)
        if match:
            destination = _clean_place_text(match.group("destination"))
            if destination:
                return None, destination

    return None, None


def _should_use_naver(origin: str, destination: str) -> bool:
    if not _has_naver_credentials():
        return False

    return _looks_like_korean_place(origin) or _looks_like_korean_place(destination)


def _resolve_naver_location(place: str) -> dict[str, Any] | None:
    normalized = _normalize_place_input(place)

    coordinates = _extract_coordinates(normalized)
    if coordinates:
        lat, lon = coordinates
        session_location = get_current_session_location()
        if session_location:
            current_lat, current_lon = session_location
            if abs(lat - current_lat) < 0.0002 and abs(lon - current_lon) < 0.0002:
                return {
                    "lat": lat,
                    "lon": lon,
                    "label": "your current location",
                }
        return {
            "lat": lat,
            "lon": lon,
            "label": normalized,
        }

    if _uses_current_location(place):
        location = get_current_session_location()
        if not location:
            return None

        lat, lon = location
        return {
            "lat": lat,
            "lon": lon,
            "label": "your current location",
        }

    response = httpx.get(
        _NAVER_GEOCODE_URL,
        params={"query": normalized},
        headers=_naver_headers(),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    addresses = data.get("addresses") or []
    if not addresses:
        return None

    best = addresses[0]
    return {
        "lat": float(best["y"]),
        "lon": float(best["x"]),
        "label": best.get("roadAddress") or best.get("jibunAddress") or normalized,
    }


def _call_naver_directions(origin: dict[str, Any], destination: dict[str, Any]) -> dict | None:
    response = httpx.get(
        _NAVER_DIRECTIONS_URL,
        params={
            "start": f"{origin['lon']},{origin['lat']}",
            "goal": f"{destination['lon']},{destination['lat']}",
            "option": "trafast",
        },
        headers=_naver_headers(),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    routes = (
        data.get("route", {}).get("trafast")
        or data.get("route", {}).get("traoptimal")
        or data.get("route", {}).get("tracomfort")
        or data.get("route", {}).get("traavoidtoll")
    )
    if not routes:
        logger.warning(
            "NAVER Directions API returned no routes: code=%s message=%s",
            data.get("code"),
            data.get("message", ""),
        )
        return None

    return routes[0]


def _get_directions_naver(destination: str, origin: str) -> dict:
    origin_info = _resolve_naver_location(origin)
    destination_info = _resolve_naver_location(destination)
    if not origin_info or not destination_info:
        return {
            "status": "error",
            "message": f"Could not resolve a Korean driving route to {destination}",
        }

    route = _call_naver_directions(origin_info, destination_info)
    if not route:
        return {
            "status": "error",
            "message": f"Could not find directions to {destination}",
        }

    summary = route.get("summary", {})
    steps = [
        _strip_html(guide.get("instructions", ""))
        for guide in route.get("guide", [])[:5]
        if guide.get("instructions")
    ]

    return {
        "status": "success",
        "provider": "naver_maps",
        "destination": destination_info["label"],
        "origin": origin_info["label"],
        "distance": _format_distance_meters(summary.get("distance", 0)),
        "duration": _format_duration_seconds(summary.get("duration", 0) / 1000),
        "travel_mode": "driving",
        "route_summary": "Real-time driving route",
        "steps": steps,
        "toll_fare_krw": summary.get("tollFare"),
        "fuel_price_krw": summary.get("fuelPrice"),
    }


def _get_eta_naver(destination: str, origin: str) -> dict:
    origin_info = _resolve_naver_location(origin)
    destination_info = _resolve_naver_location(destination)
    if not origin_info or not destination_info:
        return {
            "status": "error",
            "message": f"Could not resolve a Korean driving ETA to {destination}",
        }

    route = _call_naver_directions(origin_info, destination_info)
    if not route:
        return {
            "status": "error",
            "message": f"Could not calculate ETA to {destination}",
        }

    summary = route.get("summary", {})
    duration_seconds = summary.get("duration", 0) / 1000
    eta = datetime.now() + timedelta(seconds=duration_seconds)

    return {
        "status": "success",
        "provider": "naver_maps",
        "destination": destination_info["label"],
        "origin": origin_info["label"],
        "duration": _format_duration_seconds(duration_seconds),
        "distance": _format_distance_meters(summary.get("distance", 0)),
        "eta": eta.strftime("%I:%M %p"),
        "traffic": "realtime",
        "toll_fare_krw": summary.get("tollFare"),
        "fuel_price_krw": summary.get("fuelPrice"),
    }


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
    destination = _normalize_place_input(destination)
    origin = _resolve_origin_input(origin)
    destination, origin = _resolve_route_endpoints(destination, origin)

    if _should_use_naver(origin, destination):
        try:
            logger.info(
                "Routing directions via NAVER Maps: origin=%s dest=%s",
                origin,
                destination,
            )
            result = _get_directions_naver(destination, origin)
            if result.get("status") == "success":
                return result
            logger.warning(
                "NAVER directions failed, falling back to Google: origin=%s dest=%s message=%s",
                origin,
                destination,
                result.get("message", ""),
            )
        except Exception as exc:
            logger.error(
                "NAVER directions error, falling back to Google: %s",
                exc,
            )

    if not _MAPS_API_KEY:
        return {
            "status": "error",
            "message": "No route provider is configured for this request.",
        }

    try:
        logger.info(
            "Routing directions via Google Maps: origin=%s dest=%s",
            origin,
            destination,
        )
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
            "provider": "google_maps",
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
        return {
            "status": "error",
            "message": f"Directions lookup failed for {destination}",
        }


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
    destination = _normalize_place_input(destination)
    origin = _resolve_origin_input(origin)
    destination, origin = _resolve_route_endpoints(destination, origin)

    if _should_use_naver(origin, destination):
        try:
            logger.info(
                "Routing ETA via NAVER Maps: origin=%s dest=%s",
                origin,
                destination,
            )
            result = _get_eta_naver(destination, origin)
            if result.get("status") == "success":
                return result
            logger.warning(
                "NAVER ETA failed, falling back to Google: origin=%s dest=%s message=%s",
                origin,
                destination,
                result.get("message", ""),
            )
        except Exception as exc:
            logger.error("NAVER ETA error, falling back to Google: %s", exc)

    if not _MAPS_API_KEY:
        return {
            "status": "error",
            "message": "No route provider is configured for this request.",
        }

    try:
        logger.info(
            "Routing ETA via Google Maps: origin=%s dest=%s",
            origin,
            destination,
        )
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
            "provider": "google_maps",
            "destination": leg["end_address"],
            "origin": leg["start_address"],
            "duration": duration_text,
            "distance": leg["distance"]["text"],
            "eta": eta.strftime("%I:%M %p"),
            "traffic": _traffic_level(leg),
        }
    except Exception as e:
        logger.error("ETA API error: %s", e)
        return {
            "status": "error",
            "message": f"ETA lookup failed for {destination}",
        }


def get_eta_from_query(query: str, current_location: str = "current location") -> dict:
    """Gets ETA from a natural-language travel-time question.

    Examples:
        - "서울에서 부산까지 얼마나 걸려?"
        - "How long does it take from Seoul to Busan?"
        - "부산까지 얼마나 걸려?"
    """
    origin, destination = _extract_route_from_query(query)
    if not destination:
        return {
            "status": "error",
            "message": (
                "I need a destination to estimate travel time. "
                "Try asking like '서울에서 부산까지 얼마나 걸려?'"
            ),
        }

    resolved_origin = _resolve_origin_input(origin or current_location)
    resolved_destination = _normalize_place_input(destination)
    result = get_eta(destination=resolved_destination, origin=resolved_origin)
    if isinstance(result, dict):
        result.setdefault("resolved_origin", resolved_origin)
        result.setdefault("resolved_destination", resolved_destination)
        result["query"] = query
    return result


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
        return {
            "status": "error",
            "message": "Google Maps API key is not configured.",
        }

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
        return {
            "status": "error",
            "message": f"Places lookup failed for '{query}'",
        }
