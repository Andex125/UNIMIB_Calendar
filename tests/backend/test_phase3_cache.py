import unittest
import io
import json
import urllib.parse
from unittest.mock import patch
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

api_cal = load_module("api_cal", "api/calendar.py")
api_opt = load_module("api_opt", "api/options.py")

class MockCalendarHandler(api_cal.handler):
    def __init__(self, path):
        self.path = path
        self.response_status = None
        self.headers = {}
        self.output = io.BytesIO()
        self.wfile = self.output
        self.do_GET()

    def send_response(self, code):
        self.response_status = code

    def send_header(self, k, v):
        self.headers[k] = v

    def end_headers(self):
        pass

    def get_json(self):
        return json.loads(self.output.getvalue().decode("utf-8"))

class MockOptionsHandler(api_opt.handler):
    def __init__(self, path):
        self.path = path
        self.response_status = None
        self.headers = {}
        self.output = io.BytesIO()
        self.wfile = self.output
        self.do_GET()

    def send_response(self, code):
        self.response_status = code

    def send_header(self, k, v):
        self.headers[k] = v

    def end_headers(self):
        pass

    def get_json(self):
        return json.loads(self.output.getvalue().decode("utf-8"))

class TestPhase3CacheHeaders(unittest.TestCase):
    def test_calendar_success_cache_headers(self):
        fake_grid = {
            "first_day_label": "07-10-2024",
            "last_day_label": "11-10-2024",
            "giorni": [{"data": "07-10-2024", "label": "Lunedì"}],
            "celle": []
        }
        with patch.object(api_cal, "fetch_unimib_grid", return_value=fake_grid):
            h = MockCalendarHandler("/api/calendar?anno=2024&corso=F1801Q&anno2=GGG%7C2&date=07-10-2024")
            self.assertEqual(h.response_status, 200)
            self.assertEqual(h.headers.get("Cache-Control"), "public, s-maxage=300, stale-while-revalidate=600")

    def test_calendar_refresh_no_store(self):
        fake_grid = {
            "first_day_label": "07-10-2024",
            "last_day_label": "11-10-2024",
            "giorni": [{"data": "07-10-2024", "label": "Lunedì"}],
            "celle": []
        }
        with patch.object(api_cal, "fetch_unimib_grid", return_value=fake_grid) as mock_fetch:
            h = MockCalendarHandler("/api/calendar?anno=2024&corso=F1801Q&anno2=GGG%7C2&date=07-10-2024&refresh=1")
            self.assertEqual(h.response_status, 200)
            self.assertEqual(h.headers.get("Cache-Control"), "no-store")
            mock_fetch.assert_called_with("2024", "F1801Q", ["GGG|2"], "07-10-2024", force_refresh=True)

    def test_calendar_invalid_param_400_no_store(self):
        h = MockCalendarHandler("/api/calendar?anno=invalid&corso=F1801Q&anno2=GGG%7C2")
        self.assertEqual(h.response_status, 400)
        self.assertEqual(h.headers.get("Cache-Control"), "no-store")

    def test_calendar_unimib_failure_502_no_store(self):
        with patch.object(api_cal, "fetch_unimib_grid", side_effect=api_cal.UnimibNetworkError("Connection refused")):
            h = MockCalendarHandler("/api/calendar?anno=2024&corso=F1801Q&anno2=GGG%7C2&date=07-10-2024")
            self.assertEqual(h.response_status, 502)
            self.assertEqual(h.headers.get("Cache-Control"), "no-store")
            data = h.get_json()
            self.assertIn("error", data)

    def test_options_success_cache_headers(self):
        with patch.object(api_opt, "get_academic_years", return_value=[{"value": "2024", "label": "2024/2025"}]):
            h = MockOptionsHandler("/api/options")
            self.assertEqual(h.response_status, 200)
            self.assertEqual(h.headers.get("Cache-Control"), "public, s-maxage=3600, stale-while-revalidate=86400")

    def test_options_error_no_store(self):
        h = MockOptionsHandler("/api/options?anno=invalid")
        self.assertEqual(h.response_status, 400)
        self.assertEqual(h.headers.get("Cache-Control"), "no-store")

        h404 = MockOptionsHandler("/api/options?anno=2024&corso=NON_EXISTENT")
        with patch.object(api_opt, "get_course_teachings", return_value=None):
            h404 = MockOptionsHandler("/api/options?anno=2024&corso=NON_EXISTENT")
            self.assertEqual(h404.response_status, 404)
            self.assertEqual(h404.headers.get("Cache-Control"), "no-store")

if __name__ == "__main__":
    unittest.main()
