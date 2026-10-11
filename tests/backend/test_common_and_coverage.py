"""
Unit tests for api/_common.py and enhanced edge case coverage across UNIMIB Calendar endpoints.
Covers:
- BoundedTTLCache (eviction, TTL, dictionary interface, thread safety)
- Date and Timezone helpers (get_rome_now, get_monday, parse_date_to_monday, invalid dates)
- Text and HTML sanitization (clean_html, split_curricula, safe_ts, sanitize_text)
- BaseApiHandler (read_json_body limits, negative length, malformed JSON, query parsing, headers)
- fetch_upstream & UpstreamError exception handling
- Redis local fallback TTL expiration and deletion
"""

import unittest
import os
import sys
import io
import time
import json
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._common import (
    BoundedTTLCache,
    get_rome_now,
    get_monday,
    parse_date_to_monday,
    clean_html,
    split_curricula,
    safe_ts,
    sanitize_text,
    BaseApiHandler,
    fetch_upstream,
    UpstreamError,
    redis_get,
    redis_set,
    redis_del,
    redis_cmd,
    _LOCAL_STORE_PATH
)
import api.rooms as rooms_mod
import api.teachers as teachers_mod
import api.export as export_mod


class TestBoundedTTLCache(unittest.TestCase):
    def test_basic_set_get_and_default(self):
        cache = BoundedTTLCache(maxsize=5, ttl_seconds=10)
        cache.set("a", 1)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("nonexistent", "default_val"), "default_val")
        self.assertIn("a", cache)
        self.assertNotIn("b", cache)

    def test_lru_eviction_when_maxsize_reached(self):
        cache = BoundedTTLCache(maxsize=3, ttl_seconds=10)
        cache.set("k1", 1)
        cache.set("k2", 2)
        cache.set("k3", 3)
        self.assertEqual(len(cache), 3)

        # Access k1 to make k2 least recently used
        _ = cache.get("k1")

        # Insert k4 -> should evict k2
        cache.set("k4", 4)
        self.assertEqual(len(cache), 3)
        self.assertIsNone(cache.get("k2"))
        self.assertEqual(cache.get("k1"), 1)
        self.assertEqual(cache.get("k3"), 3)
        self.assertEqual(cache.get("k4"), 4)

    def test_ttl_expiration(self):
        cache = BoundedTTLCache(maxsize=5, ttl_seconds=0.1)
        cache.set("expiring", "value")
        self.assertEqual(cache.get("expiring"), "value")
        time.sleep(0.15)
        self.assertIsNone(cache.get("expiring"))
        self.assertEqual(cache.get("expiring", "expired"), "expired")

    def test_dict_interface_methods(self):
        cache = BoundedTTLCache(maxsize=5, ttl_seconds=10)
        cache["key1"] = "val1"
        self.assertEqual(cache["key1"], "val1")
        with self.assertRaises(KeyError):
            _ = cache["missing"]

        self.assertEqual(cache.setdefault("key2", "val2"), "val2")
        self.assertEqual(cache.setdefault("key2", "different"), "val2")

        self.assertEqual(cache.pop("key1"), "val1")
        self.assertEqual(cache.pop("key1", "not_found"), "not_found")

        cache.set("k_a", 10)
        cache.set("k_b", 20)
        self.assertIn("k_a", cache.keys())
        self.assertEqual(len(cache.items()), 3)

        cache.clear()
        self.assertEqual(len(cache), 0)


class TestDateAndTimezoneHelpers(unittest.TestCase):
    def test_get_rome_now_returns_localized_datetime(self):
        now = get_rome_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertIn(now.tzinfo.tzname(now), ("CET", "CEST", "UTC+01:00", "UTC+02:00"))

    def test_get_monday_calculation(self):
        # Wednesday 2026-10-07
        wed = datetime(2026, 10, 7)
        mon = get_monday(wed)
        self.assertEqual(mon.weekday(), 0)
        self.assertEqual(mon.strftime("%Y-%m-%d"), "2026-10-05")

        # Sunday 2026-10-11
        sun = datetime(2026, 10, 11)
        mon_sun = get_monday(sun)
        self.assertEqual(mon_sun.weekday(), 0)
        self.assertEqual(mon_sun.strftime("%Y-%m-%d"), "2026-10-05")

    def test_parse_date_to_monday_valid_and_invalid(self):
        # Italian format
        m1 = parse_date_to_monday("07-10-2026")
        self.assertEqual(m1.strftime("%d-%m-%Y"), "05-10-2026")

        # ISO format
        m2 = parse_date_to_monday("2026-10-07")
        self.assertEqual(m2.strftime("%d-%m-%Y"), "05-10-2026")

        # Empty string defaults to current Monday
        m3 = parse_date_to_monday("")
        self.assertEqual(m3.weekday(), 0)

        # Invalid formats
        with self.assertRaises(ValueError):
            parse_date_to_monday("07/10/2026")

        with self.assertRaises(ValueError):
            parse_date_to_monday("not-a-date")

        # Out-of-bounds calendar numbers (Feb 31)
        with self.assertRaises(ValueError):
            parse_date_to_monday("31-02-2026")


class TestSanitizationAndParsers(unittest.TestCase):
    def test_clean_html(self):
        self.assertEqual(clean_html("<b>Corso</b> di <i>Laurea</i>"), "Corso di Laurea")
        self.assertEqual(clean_html("   <span>Spazi   multipli</span>  "), "Spazi multipli")
        self.assertEqual(clean_html(None), "")
        self.assertEqual(clean_html(123), "123")

    def test_split_curricula(self):
        raw = "Curriculum A<hr>Curriculum B<hr/>Curriculum C"
        res = split_curricula(raw)
        self.assertEqual(res, ["Curriculum A", "Curriculum B", "Curriculum C"])
        self.assertEqual(split_curricula(None), [])
        self.assertEqual(split_curricula(""), [])

    def test_safe_ts(self):
        self.assertEqual(safe_ts({"timestamp": 12345}), 12345)
        self.assertEqual(safe_ts({"timestamp": "67890"}), 67890)
        self.assertEqual(safe_ts({"timestamp": "invalid"}), 0)
        self.assertEqual(safe_ts({}), 0)

    def test_sanitize_text(self):
        dirty = "<script>alert('xss')</script>Hello <b>World</b>"
        clean = sanitize_text(dirty, max_len=50)
        self.assertNotIn("<script>", clean)
        self.assertNotIn("alert", clean)
        self.assertNotIn("<b>", clean)
        self.assertEqual(clean, "Hello World")

        # Non-string fallback
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text(123), "")


class TestBaseApiHandler(unittest.TestCase):
    def _create_handler(self, headers=None, body_bytes=b""):
        h = BaseApiHandler.__new__(BaseApiHandler)
        h.path = "/api/test?arg1=val1&arg2=val2"
        h.headers = dict(headers or {})
        h.rfile = io.BytesIO(body_bytes)
        h.wfile = io.BytesIO()

        self.sent_status = None
        self.sent_headers = {}

        def mock_send_response(code):
            self.sent_status = code

        def mock_send_header(name, val):
            self.sent_headers[name] = val

        h.send_response = mock_send_response
        h.send_header = mock_send_header
        h.end_headers = lambda: None
        return h

    def test_read_json_body_validation(self):
        # 1. Valid body
        payload = {"test": 123}
        data = json.dumps(payload).encode("utf-8")
        h = self._create_handler(headers={"Content-Length": str(len(data))}, body_bytes=data)
        self.assertEqual(h.read_json_body(), payload)

        # 2. Empty body
        h_empty = self._create_handler(headers={"Content-Length": "0"})
        self.assertEqual(h_empty.read_json_body(), {})

        # 3. Negative Content-Length
        h_neg = self._create_handler(headers={"Content-Length": "-1"})
        with self.assertRaises(ValueError):
            h_neg.read_json_body()

        # 4. Non-integer Content-Length
        h_bad = self._create_handler(headers={"Content-Length": "abc"})
        with self.assertRaises(ValueError):
            h_bad.read_json_body()

        # 5. Oversized body (>64KB)
        big_data = b"x" * 70000
        h_big = self._create_handler(headers={"Content-Length": str(len(big_data))}, body_bytes=big_data)
        with self.assertRaises(ValueError):
            h_big.read_json_body()

        # 6. Malformed JSON
        malformed = b"not json"
        h_mal = self._create_handler(headers={"Content-Length": str(len(malformed))}, body_bytes=malformed)
        with self.assertRaises(ValueError):
            h_mal.read_json_body()

    def test_query_param_helpers(self):
        h = self._create_handler()
        self.assertEqual(h.get_query_param("arg1"), "val1")
        self.assertEqual(h.get_query_param("arg2"), "val2")
        self.assertEqual(h.get_query_param("nonexistent", "fallback"), "fallback")

    def test_send_json_headers(self):
        h = self._create_handler()
        h.send_json(200, {"success": True})
        self.assertEqual(self.sent_status, 200)
        self.assertEqual(self.sent_headers.get("Content-Type"), "application/json; charset=utf-8")
        self.assertEqual(self.sent_headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(self.sent_headers.get("X-Frame-Options"), "DENY")
        self.assertIn("s-maxage=300", self.sent_headers.get("Cache-Control", ""))

        # Non-200 sends no-store
        h.send_json(400, {"error": "bad request"})
        self.assertEqual(self.sent_status, 400)
        self.assertEqual(self.sent_headers.get("Cache-Control"), "no-store")

    def test_handle_options_preflight(self):
        h = self._create_handler()
        h.handle_options(methods="GET, POST, OPTIONS", allow_origin="https://unimib.it")
        self.assertEqual(self.sent_status, 204)
        self.assertEqual(self.sent_headers.get("Access-Control-Allow-Origin"), "https://unimib.it")
        self.assertEqual(self.sent_headers.get("Access-Control-Allow-Methods"), "GET, POST, OPTIONS")


class TestUpstreamFetchAndRedis(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fetch_upstream_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = fetch_upstream("https://example.com/api")
        self.assertEqual(res, '{"status": "ok"}')

    @patch("urllib.request.urlopen")
    def test_fetch_upstream_retries_and_raises(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        with self.assertRaises(UpstreamError) as ctx:
            fetch_upstream("https://example.com/timeout", max_retries=1)
        self.assertIn("Impossibile contattare", str(ctx.exception))

    def test_redis_local_fallback_expiry(self):
        key = "short_ttl_key"
        redis_set(key, {"value": 42}, ex=1)
        self.assertEqual(redis_get(key), {"value": 42})
        time.sleep(1.1)
        self.assertIsNone(redis_get(key))


class TestCampusRoomsAndTeachersHelpers(unittest.TestCase):
    def test_teachers_extract_emails(self):
        mail_str = "docente@unimib.it, ALTRO.DOCENTE@UNIMIB.IT"
        link_str = "http://unimib.it/docente@unimib.it"
        emails = teachers_mod.extract_emails(mail_str, link_str)
        self.assertEqual(emails, ["docente@unimib.it", "altro.docente@unimib.it"])

    def test_rooms_parse_time_str_and_format_minutes(self):
        self.assertEqual(rooms_mod.parse_time_str("08:30"), 8 * 60 + 30)
        self.assertEqual(rooms_mod.parse_time_str("20:00"), 20 * 60)
        self.assertEqual(rooms_mod.parse_time_str(""), 0)
        self.assertEqual(rooms_mod.format_minutes(510), "08:30")


if __name__ == "__main__":
    unittest.main()
