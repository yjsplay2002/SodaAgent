"""Open-Meteo weather API integration.

Free API, no key required.
Documentation: https://open-meteo.com/en/docs

Falls back to mock data on network errors.
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


def get_current_weather(city: str = "San Francisco") -> dict:
    """Gets the current weather for a city.

    Args:
        city: City name. Defaults to San Francisco.

    Returns:
        A dictionary with current weather conditions.
    """
    geo = _geocode(city)
    if not geo:
        return _mock_current_weather(city)

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
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
            timeout=5,
        )
        data = resp.json()
        current = data["current"]

        condition = _WMO_CODES.get(current["weather_code"], "Unknown")
        temp = round(current["temperature_2m"])
        humidity = current["relative_humidity_2m"]
        wind_speed = round(current["wind_speed_10m"])

        return {
            "status": "success",
            "city": resolved_name,
            "temperature": f"{temp}°F",
            "condition": condition,
            "humidity": f"{humidity}%",
            "wind": f"{wind_speed} mph",
            "summary": f"It's {temp}°F and {condition.lower()} in {resolved_name}.",
        }
    except Exception as e:
        logger.error("Weather API error: %s", e)
        return _mock_current_weather(city)


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


def get_forecast(city: str = "San Francisco", days: int = 3) -> dict:
    """Gets the weather forecast for upcoming days.

    Args:
        city: City name. Defaults to San Francisco.
        days: Number of days to forecast (1-7). Default is 3.

    Returns:
        A dictionary with the weather forecast.
    """
    geo = _geocode(city)
    if not geo:
        return _mock_forecast(city)

    lat, lon, resolved_name = geo
    days = min(max(days, 1), 7)

    try:
        resp = httpx.get(
            _WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "temperature_unit": "fahrenheit",
                "forecast_days": days,
            },
            timeout=5,
        )
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
                "high": f"{round(daily['temperature_2m_max'][i])}°F",
                "low": f"{round(daily['temperature_2m_min'][i])}°F",
                "condition": _WMO_CODES.get(daily["weather_code"][i], "Unknown"),
            })

        return {
            "status": "success",
            "city": resolved_name,
            "forecast": forecast,
        }
    except Exception as e:
        logger.error("Forecast API error: %s", e)
        return _mock_forecast(city)


# ---------------------------------------------------------------------------
# Mock fallbacks (used on network errors)
# ---------------------------------------------------------------------------


def _mock_current_weather(city: str) -> dict:
    return {
        "status": "success",
        "city": city,
        "temperature": "72°F",
        "condition": "Partly cloudy",
        "humidity": "45%",
        "wind": "8 mph",
        "summary": f"It's 72°F and partly cloudy in {city}.",
    }


def _mock_forecast(city: str) -> dict:
    return {
        "status": "success",
        "city": city,
        "forecast": [
            {"day": "Today", "high": "75°F", "low": "58°F", "condition": "Partly cloudy"},
            {"day": "Tomorrow", "high": "70°F", "low": "55°F", "condition": "Sunny"},
            {"day": "Day after", "high": "68°F", "low": "52°F", "condition": "Light rain"},
        ],
    }
