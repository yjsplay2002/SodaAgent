import sys
import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_BACKEND_ROOT = Path(__file__).resolve().parents[1]

sys.modules.setdefault("httpx", SimpleNamespace(get=None))


def _load_module(name: str, relative_path: str):
    module_path = _BACKEND_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


maps_tools = _load_module("maps_tools_test", "soda_agent/tools/maps_tools.py")
weather_tools = _load_module(
    "weather_tools_test",
    "soda_agent/tools/weather_tools.py",
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class LocationAwareToolsTest(unittest.TestCase):
    def test_maps_normalizes_coordinate_context_sentence(self):
        value = (
            "[Context only] Device location coordinates: 37.56650,126.97800. "
            "Use these coordinates for tool arguments."
        )

        self.assertEqual(
            maps_tools._normalize_place_input(value),
            "37.56650,126.97800",
        )

    def test_weather_extracts_legacy_coordinate_sentence(self):
        value = (
            "The user is currently near latitude 37.56650 and longitude 126.97800."
        )

        self.assertEqual(
            weather_tools._extract_coordinates(value),
            (37.5665, 126.978),
        )

    def test_weather_accepts_coordinates_without_geocoding(self):
        with patch.object(weather_tools.httpx, "get") as mock_get:
            mock_get.return_value = _FakeResponse(
                {
                    "current": {
                        "temperature_2m": 12.4,
                        "relative_humidity_2m": 55,
                        "weather_code": 3,
                        "wind_speed_10m": 8.1,
                        "wind_direction_10m": 180,
                    }
                }
            )

            result = weather_tools.get_current_weather("37.56650,126.97800")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["city"], "your current location")
        self.assertIn("near your current location", result["summary"])


if __name__ == "__main__":
    unittest.main()
