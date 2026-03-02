def get_directions(destination: str) -> dict:
    """Gets driving directions to a destination.

    Args:
        destination: The destination address or place name.

    Returns:
        A dictionary with route information including distance and ETA.
    """
    # MVP: Mock data. Production: Google Maps Directions API
    return {
        "status": "success",
        "destination": destination,
        "distance": "12.3 miles",
        "duration": "25 minutes",
        "summary": f"Head north on Highway 101, then take exit 42B toward {destination}. "
        "The route looks clear with no major traffic.",
    }


def get_eta(destination: str) -> dict:
    """Gets the estimated time of arrival to a destination.

    Args:
        destination: The destination address or place name.

    Returns:
        A dictionary with ETA information.
    """
    from datetime import datetime, timedelta

    eta = datetime.now() + timedelta(minutes=25)
    return {
        "status": "success",
        "destination": destination,
        "eta": eta.strftime("%I:%M %p"),
        "duration": "25 minutes",
        "traffic": "light",
    }


def search_places(query: str, category: str = "general") -> dict:
    """Searches for nearby places matching the query.

    Args:
        query: Search query like 'gas station', 'coffee shop', 'restaurant'.
        category: Category filter. Options: general, food, gas, parking, charging.

    Returns:
        A dictionary with matching places.
    """
    return {
        "status": "success",
        "query": query,
        "results": [
            {
                "name": f"Best {query.title()} Nearby",
                "distance": "0.8 miles",
                "rating": 4.5,
                "open": True,
            },
            {
                "name": f"{query.title()} Express",
                "distance": "1.2 miles",
                "rating": 4.2,
                "open": True,
            },
        ],
    }
