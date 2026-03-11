import sys
import unittest
import importlib.util
import importlib
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
live_tool_context = importlib.import_module("services.live_tool_context")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class LocationAwareToolsTest(unittest.TestCase):
    def setUp(self):
        live_tool_context.clear_session_location("test-session")

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

    def test_maps_uses_session_location_for_current_origin(self):
        token = live_tool_context.set_active_session("test-session")
        live_tool_context.set_session_location("test-session", 37.5665, 126.9780)
        try:
            self.assertEqual(
                maps_tools._resolve_origin_input("current location"),
                "37.56650,126.97800",
            )
        finally:
            live_tool_context.reset_active_session(token)

    def test_weather_strips_query_suffix_from_city(self):
        self.assertEqual(
            weather_tools._normalize_city("성남 분당구 날씨"),
            "성남 분당구",
        )

    def test_maps_prefers_naver_for_korean_current_location_route(self):
        token = live_tool_context.set_active_session("test-session")
        live_tool_context.set_session_location("test-session", 37.5665, 126.9780)
        try:
            with (
                patch.object(maps_tools, "_NAVER_MAPS_API_KEY_ID", "test-id"),
                patch.object(maps_tools, "_NAVER_MAPS_API_KEY", "test-key"),
            ):
                self.assertTrue(
                    maps_tools._should_use_naver(
                        "37.56650,126.97800",
                        "서울역",
                    )
                )
        finally:
            live_tool_context.reset_active_session(token)

    def test_maps_get_eta_uses_naver_for_korean_route(self):
        token = live_tool_context.set_active_session("test-session")
        live_tool_context.set_session_location("test-session", 37.5665, 126.9780)
        try:
            with (
                patch.object(maps_tools, "_NAVER_MAPS_API_KEY_ID", "test-id"),
                patch.object(maps_tools, "_NAVER_MAPS_API_KEY", "test-key"),
                patch.object(maps_tools.httpx, "get") as mock_get,
            ):
                def fake_get(url, params=None, headers=None, timeout=None):
                    if url.startswith(maps_tools._NAVER_GEOCODE_URL):
                        return _FakeResponse(
                            {
                                "addresses": [
                                    {
                                        "x": "127.00110",
                                        "y": "37.57000",
                                        "roadAddress": "서울특별시 중구 서울역",
                                    }
                                ]
                            }
                        )

                    if url.startswith(maps_tools._NAVER_DIRECTIONS_URL):
                        return _FakeResponse(
                            {
                                "route": {
                                    "trafast": [
                                        {
                                            "summary": {
                                                "distance": 12345,
                                                "duration": 1800000,
                                                "tollFare": 0,
                                                "fuelPrice": 2400,
                                            },
                                            "guide": [
                                                {"instructions": "직진"},
                                                {"instructions": "좌회전"},
                                            ],
                                        }
                                    ]
                                }
                            }
                        )

                    raise AssertionError(f"Unexpected URL: {url}")

                mock_get.side_effect = fake_get

                result = maps_tools.get_eta("서울역", "current location")

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["provider"], "naver_maps")
            self.assertEqual(result["origin"], "your current location")
            self.assertEqual(result["destination"], "서울특별시 중구 서울역")
            self.assertEqual(result["distance"], "12.3 km")
            self.assertEqual(result["duration"], "30 min")
            self.assertEqual(result["traffic"], "realtime")
        finally:
            live_tool_context.reset_active_session(token)


if __name__ == "__main__":
    unittest.main()
