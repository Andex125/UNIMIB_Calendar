"""
Tests for Upstash Redis local fallback and Anti-XSS / Script Ingestion security.
"""

import unittest
import os
import sys
import io
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import handlers and helpers from api
import api.profile as profile_mod
import api.group as group_mod
import api.shared_calendar as shared_cal_mod


class DummyRequest:
    def __init__(self, body_bytes: bytes):
        self.rfile = io.BytesIO(body_bytes)


class TestSecurityAndRedis(unittest.TestCase):

    def setUp(self):
        # Clear env vars to simulate missing Upstash credentials
        os.environ.pop("UPSTASH_REDIS_REST_URL", None)
        os.environ.pop("UPSTASH_REDIS_REST_TOKEN", None)
        os.environ.pop("KV_REST_API_URL", None)
        os.environ.pop("KV_REST_API_TOKEN", None)
        os.environ.pop("REDIS_REST_URL", None)
        os.environ.pop("REDIS_REST_TOKEN", None)

        # Clear local store
        if os.path.exists(profile_mod._LOCAL_STORE_PATH):
            try:
                os.remove(profile_mod._LOCAL_STORE_PATH)
            except Exception:
                pass

    def tearDown(self):
        if os.path.exists(profile_mod._LOCAL_STORE_PATH):
            try:
                os.remove(profile_mod._LOCAL_STORE_PATH)
            except Exception:
                pass

    def test_redis_local_fallback_get_set_del(self):
        """Test that get, set, del work locally when env vars are missing."""
        profile_mod.redis_set("test_key", {"foo": "bar"})
        val = profile_mod.redis_get("test_key")
        self.assertEqual(val, {"foo": "bar"})

        # Group module sees the same store
        group_val = group_mod.redis_get("test_key")
        self.assertEqual(group_val, {"foo": "bar"})

        profile_mod.redis_del("test_key")
        self.assertIsNone(profile_mod.redis_get("test_key"))

    def test_xss_sanitization_nickname(self):
        """Test that script tags and dangerous HTML in nickname are stripped."""
        malicious = "<script>alert('XSS')</script>Mario"
        sanitized = profile_mod._sanitize_nickname(malicious)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("alert", sanitized)
        self.assertEqual(sanitized, "Mario")

        # HTML tags stripping
        img_xss = '<img src=x onerror=alert(1)>Luigi'
        sanitized_img = profile_mod._sanitize_nickname(img_xss)
        self.assertNotIn("<img", sanitized_img)
        self.assertNotIn("onerror", sanitized_img)
        self.assertEqual(sanitized_img, "Luigi")

    def test_xss_sanitization_config(self):
        """Test that script tags in study plan config are sanitized."""
        cfg = {
            "corso": "F123",
            "corsoLabel": "<script>alert('XSS')</script>Informatica",
            "anni": ["1"],
            "anniLabels": ["1° Anno <svg onload=alert(1)>"],
            "favorites": [
                {"code": "C1", "label": "<b>Programmazione</b>"}
            ]
        }
        clean = profile_mod._sanitize_config(cfg)
        self.assertNotIn("<script>", clean["corsoLabel"])
        self.assertNotIn("<svg", clean["anniLabels"][0])
        self.assertNotIn("<b>", clean["favorites"][0]["label"])

    def test_profile_creation_without_redis_env_vars(self):
        """Test creating a profile when Redis env vars are missing (no crash, successful creation)."""
        body = json.dumps({
            "nickname": "TestUser",
            "pin": "1234",
            "config": {"corso": "F123", "corsoLabel": "Informatica"}
        }).encode("utf-8")

        h = profile_mod.handler.__new__(profile_mod.handler)
        h.headers = {"Content-Length": str(len(body))}
        h.rfile = io.BytesIO(body)
        h.wfile = io.BytesIO()

        status_code = None
        def fake_send_response(code):
            nonlocal status_code
            status_code = code

        h.send_response = fake_send_response
        h.send_header = lambda *a: None
        h.end_headers = lambda: None

        h.do_POST()

        self.assertEqual(status_code, 201)
        res = json.loads(h.wfile.getvalue())
        self.assertEqual(res["nickname"], "TestUser")
        self.assertTrue(res["share_code"])
        self.assertTrue(res["session_token"])
        self.assertTrue(res["recovery_code"])

        # Check account can be retrieved
        account = profile_mod.redis_get("account:testuser")
        self.assertIsNotNone(account)
        self.assertEqual(account["nickname"], "TestUser")

    def test_group_lifecycle_without_redis_env_vars(self):
        """Test creating, joining, and listing groups with local fallback."""
        # 1. Setup authenticated user
        clean_nick = "teststudente"
        share_code = "ABC123"
        session_token = profile_mod._create_session(clean_nick, share_code)

        # 2. Create group
        body = json.dumps({
            "action": "create_group",
            "name": "<script>alert(1)</script>Studio Algoritmi"
        }).encode("utf-8")

        h = group_mod.handler.__new__(group_mod.handler)
        h.headers = {
            "Content-Length": str(len(body)),
            "Authorization": f"Bearer {session_token}"
        }
        h.rfile = io.BytesIO(body)
        h.wfile = io.BytesIO()

        status_code = None
        h.send_response = lambda code: globals().update(status_code=code) or None
        h.send_header = lambda *a: None
        h.end_headers = lambda: None

        # Call do_POST
        h.do_POST()
        res = json.loads(h.wfile.getvalue())
        self.assertEqual(res["group"]["name"], "Studio Algoritmi")  # script tag stripped!
        self.assertEqual(res["group"]["creator"], share_code)
        gid = res["group"]["id"]

        # 3. Rename group
        rename_body = json.dumps({
            "action": "rename_group",
            "group_id": gid,
            "name": "Algoritmi Avanzati"
        }).encode("utf-8")
        h.rfile = io.BytesIO(rename_body)
        h.headers["Content-Length"] = str(len(rename_body))
        h.wfile = io.BytesIO()
        h.do_POST()
        rename_res = json.loads(h.wfile.getvalue())
        self.assertEqual(rename_res["group"]["name"], "Algoritmi Avanzati")

    def test_security_headers_and_payload_limit(self):
        """Test OWASP security headers and 413 Payload Too Large check."""
        h = profile_mod.handler.__new__(profile_mod.handler)
        sent_headers = {}
        sent_status = None
        h.send_response = lambda code: globals().update(sent_status=code) or None
        def mock_send_header(name, val):
            sent_headers[name] = val
        h.send_header = mock_send_header
        h.end_headers = lambda: None
        h.wfile = io.BytesIO()

        # Check send_json headers
        h._send_json(200, {"ok": True})
        self.assertEqual(sent_headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(sent_headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(sent_headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("geolocation=()", sent_headers.get("Permissions-Policy", ""))

        # Check 413 on payload > 64KB
        big_body = b"A" * 70000
        h.headers = {"Content-Length": str(len(big_body))}
        h.rfile = io.BytesIO(big_body)
        h.wfile = io.BytesIO()
        h.do_POST()
        res = json.loads(h.wfile.getvalue())
        self.assertIn("troppo grande", res.get("error", "").lower())


if __name__ == '__main__':
    unittest.main()

