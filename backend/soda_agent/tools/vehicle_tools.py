def get_vehicle_status() -> dict:
    """Gets the current vehicle status including fuel, battery, and diagnostics.

    Returns:
        A dictionary with vehicle status information.
    """
    return {
        "status": "success",
        "fuel_level": "65%",
        "range": "280 miles",
        "tire_pressure": "All normal (32 PSI)",
        "engine": "Normal",
        "oil_life": "78%",
        "next_service": "In 3,200 miles",
    }
