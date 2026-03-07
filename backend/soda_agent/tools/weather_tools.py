"""Open-Meteo weather API integration.

Free API, no key required.
Documentation: https://open-meteo.com/en/docs
"""

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

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
    try:
        resp = httpx.get(
            _GEOCODING_URL,
            params={"name": city, "count": 1, "language": "en"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("results"):
            return None
        r = data["results"][0]
        return r["latitude"], r["longitude"], r.get("name", city)
    except Exception as e:
        logger.error("Geocoding error for '%s': %s", city, e)
        return None


# ---------------------------------------------------------------------------
# get_current_weather
# ---------------------------------------------------------------------------


def get_current_weather(city: str | None = None) -> dict:
    """Gets the current weather for a city.

    Args:
        city: City name.

    Returns:
        A dictionary with current weather conditions.
    """
    city = _normalize_city(city)
    if not city:
        return _weather_city_required()

    geo = _geocode(city)
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

        return {
            "status": "success",
            "city": resolved_name,
            "temperature": f"{temp}°C",
            "condition": condition,
            "humidity": f"{humidity}%",
            "wind": f"{wind_speed} mph",
            "summary": f"It's {temp}°C and {condition.lower()} in {resolved_name}.",
        }
    except Exception as e:
        logger.error("Weather API error: %s", e)
        return _weather_unavailable(city)


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


def get_forecast(city: str | None = None, days: int = 3) -> dict:
    """Gets the weather forecast for upcoming days.

    Args:
        city: City name.
        days: Number of days to forecast (1-7). Default is 3.

    Returns:
        A dictionary with the weather forecast.
    """
    city = _normalize_city(city)
    if not city:
        return _weather_city_required()

    geo = _geocode(city)
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
                "high": f"{round(daily['temperature_2m_max'][i])}°C",
                "low": f"{round(daily['temperature_2m_min'][i])}°C",
                "condition": _WMO_CODES.get(daily["weather_code"][i], "Unknown"),
            })

        return {
            "status": "success",
            "city": resolved_name,
            "forecast": forecast,
        }
    except Exception as e:
        logger.error("Forecast API error: %s", e)
        return _forecast_unavailable(city)


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
        return None

    normalized = city.strip()
    return normalized or None
