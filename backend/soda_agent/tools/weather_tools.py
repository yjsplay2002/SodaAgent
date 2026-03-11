"""Open-Meteo weather API integration.

Free API, no key required.
Documentation: https://open-meteo.com/en/docs
"""

import logging
import re
from datetime import datetime

import httpx
from services.live_tool_context import get_current_session_location

logger = logging.getLogger(__name__)

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
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
_WEATHER_QUERY_SUFFIX_RE = re.compile(
    r"\s*(?:날씨|기온|예보|forecast|weather|현재)\s*$",
    re.IGNORECASE,
)

# WMO Weather interpretation codes → human-readable descriptions
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _geocode(city: str) -> tuple[float, float, str] | None:
    """Resolve city name to (latitude, longitude, resolved_name)."""
    for candidate in _geocode_candidates(city):
        for language in ("ko", "en"):
            try:
                resp = httpx.get(
                    _GEOCODING_URL,
                    params={"name": candidate, "count": 1, "language": language},
                    timeout=5,
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("results"):
                    continue
                r = data["results"][0]
                return r["latitude"], r["longitude"], r.get("name", candidate)
            except Exception as e:
                logger.error(
                    "Geocoding error for '%s' (language=%s): %s",
                    candidate,
                    language,
                    e,
                )
    return None


def _geocode_candidates(city: str) -> list[str]:
    normalized = city.strip()
    candidates = [normalized]

    stripped = _WEATHER_QUERY_SUFFIX_RE.sub("", normalized).strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)

    if stripped.endswith(("시", "군", "구")):
        trimmed = stripped[:-1].strip()
        if trimmed and trimmed not in candidates:
            candidates.append(trimmed)

    return candidates


def _extract_coordinates(location: str) -> tuple[float, float] | None:
    normalized = " ".join(location.split())
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
            return lat, lon
    return None


def _resolve_location(location: str) -> tuple[float, float, str] | None:
    coordinates = _extract_coordinates(location)
    if coordinates:
        lat, lon = coordinates
        return lat, lon, "your current location"

    if _uses_current_location(location):
        current_location = get_current_session_location()
        if current_location:
            lat, lon = current_location
            return lat, lon, "your current location"

    return _geocode(location)


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
        "your current location",
        "현재 위치",
        "지금 위치",
        "내 위치",
        "현위치",
    }


# ---------------------------------------------------------------------------
# get_current_weather
# ---------------------------------------------------------------------------


def get_current_weather(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Gets the current weather for a city or coordinates.
    Args:
        city: City name or coordinates as "lat,lon".
        latitude: Latitude of the user's current location. Use with longitude.
        longitude: Longitude of the user's current location. Use with latitude.
    Returns:
        A dictionary with current weather conditions.
    """
    # Prefer explicit lat/lon coordinates when provided
    if latitude is not None and longitude is not None:
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            lat, lon, resolved_name = latitude, longitude, "your current location"
        else:
            return _weather_unavailable("invalid coordinates")
    else:
        city = _normalize_city(city)
        if not city:
            return _weather_city_required()

        geo = _resolve_location(city)
        if not geo:
            return _weather_unavailable(city)
        lat, lon, resolved_name = geo

    try:
        resp = httpx.get(
            _WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "weather_code,wind_speed_10m,wind_direction_10m"
                ),
                "temperature_unit": "celsius",
                "wind_speed_unit": "mph",
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        current = data["current"]
        condition = _WMO_CODES.get(current["weather_code"], "Unknown")
        temp = round(current["temperature_2m"])
        humidity = current["relative_humidity_2m"]
        wind_speed = round(current["wind_speed_10m"])
        summary_location = (
            "near your current location"
            if resolved_name == "your current location"
            else f"in {resolved_name}"
        )
        return {
            "status": "success",
            "city": resolved_name,
            "temperature": f"{temp}\u00b0C",
            "condition": condition,
            "humidity": f"{humidity}%",
            "wind": f"{wind_speed} mph",
            "summary": f"It's {temp}\u00b0C and {condition.lower()} {summary_location}.",
        }
    except Exception as e:
        logger.error("Weather API error: %s", e)
        return _weather_unavailable(city or "current location")


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


def get_forecast(
    city: str | None = None,
    days: int = 3,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Gets the weather forecast for upcoming days.
    Args:
        city: City name or coordinates as "lat,lon".
        days: Number of days to forecast (1-7). Default is 3.
        latitude: Latitude of the user's current location. Use with longitude.
        longitude: Longitude of the user's current location. Use with latitude.
    Returns:
        A dictionary with the weather forecast.
    """
    # Prefer explicit lat/lon coordinates when provided
    if latitude is not None and longitude is not None:
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            lat, lon, resolved_name = latitude, longitude, "your current location"
        else:
            return _forecast_unavailable("invalid coordinates")
    else:
        city = _normalize_city(city)
        if not city:
            return _weather_city_required()

        geo = _resolve_location(city)
        if not geo:
            return _forecast_unavailable(city)
        lat, lon, resolved_name = geo

    days = min(max(days, 1), 7)

    try:
        resp = httpx.get(
            _WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "temperature_unit": "celsius",
                "forecast_days": days,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data["daily"]
        forecast = []
        for i in range(len(daily["time"])):
            date = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            if i == 0:
                day_label = "Today"
            elif i == 1:
                day_label = "Tomorrow"
            else:
                day_label = date.strftime("%A")
            forecast.append({
                "day": day_label,
                "high": f"{round(daily['temperature_2m_max'][i])}\u00b0C",
                "low": f"{round(daily['temperature_2m_min'][i])}\u00b0C",
                "condition": _WMO_CODES.get(daily["weather_code"][i], "Unknown"),
            })
        return {
            "status": "success",
            "city": resolved_name,
            "forecast": forecast,
        }
    except Exception as e:
        logger.error("Forecast API error: %s", e)
        return _forecast_unavailable(city or "current location")


# ---------------------------------------------------------------------------
# Error fallbacks
# ---------------------------------------------------------------------------


def _weather_unavailable(city: str) -> dict:
    return {
        "status": "error",
        "city": city,
        "message": f"Unable to fetch live weather data for {city} right now.",
        "summary": f"I couldn't fetch live weather data for {city} right now.",
    }


def _weather_city_required() -> dict:
    return {
        "status": "error",
        "message": "A city or current location is required to fetch accurate weather data.",
        "summary": "I need a city or your current location to fetch accurate weather data.",
    }


def _forecast_unavailable(city: str) -> dict:
    return {
        "status": "error",
        "city": city,
        "message": f"Unable to fetch live forecast data for {city} right now.",
        "summary": f"I couldn't fetch the live forecast for {city} right now.",
    }


def _normalize_city(city: str | None) -> str | None:
    if city is None:
        if get_current_session_location():
            return "your current location"
        return None

    normalized = _WEATHER_QUERY_SUFFIX_RE.sub("", city.strip()).strip()
    if _uses_current_location(normalized):
        return "your current location"
    return normalized or None
