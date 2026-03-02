def get_current_weather(city: str = "current location") -> dict:
    """Gets the current weather for a city or the user's current location.

    Args:
        city: City name or 'current location' for GPS-based weather.

    Returns:
        A dictionary with current weather conditions.
    """
    return {
        "status": "success",
        "city": city,
        "temperature": "72°F",
        "condition": "Partly cloudy",
        "humidity": "45%",
        "wind": "8 mph from the west",
        "summary": f"It's 72 degrees and partly cloudy in {city}. "
        "A pleasant day for driving with no rain expected.",
    }


def get_forecast(city: str = "current location", days: int = 3) -> dict:
    """Gets the weather forecast for upcoming days.

    Args:
        city: City name or 'current location'.
        days: Number of days to forecast. Default is 3.

    Returns:
        A dictionary with the weather forecast.
    """
    return {
        "status": "success",
        "city": city,
        "forecast": [
            {"day": "Today", "high": "75°F", "low": "58°F", "condition": "Partly cloudy"},
            {"day": "Tomorrow", "high": "70°F", "low": "55°F", "condition": "Sunny"},
            {"day": "Day after", "high": "68°F", "low": "52°F", "condition": "Light rain"},
        ],
    }
