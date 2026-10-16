import unittest
import json
import io
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.profile import handler as ProfileHandler, cascade_wipe_account, redis_set, redis_get, redis_del
from api._common import BaseApiHandler


class TestGdprAndAnonymization(unittest.TestCase):
    def setUp(self):
        # Clean test keys
        redis_del("account:test_gdpr_user")
        redis_del("share:tst999")
        redis_del("user_groups:tst999")
        redis_del("group:G_TEST_99")
        redis_del("session:test_gdpr_token")
        redis_del("ratelimit:login:test_gdpr_user")

    def tearDown(self):
        redis_del("account:test_gdpr_user")
        redis_del("share:tst999")
        redis_del("user_groups:tst999")
        redis_del("group:G_TEST_99")
        redis_del("session:test_gdpr_token")
        redis_del("ratelimit:login:test_gdpr_user")

    def test_cascade_wipe_account(self):
        # 1. Setup mock account, share, groups, and rate-limit keys
        clean_nick = "test_gdpr_user"
        share_code = "TST999"
        share_lower = "tst999"

        redis_set(f"account:{clean_nick}", {
            "nickname": "Mario Rossi",
            "email": "m.rossi@campus.unimib.it",
            "share_code": share_code,
            "config": {"anno": "2024", "corso": "E3101Q"}
        })
        redis_set(f"share:{share_lower}", {
            "nickname": "Mario Rossi",
            "share_code": share_code,
            "config": {"anno": "2024"}
        })
        redis_set(f"user_groups:{share_lower}", ["G_TEST_99"])
        redis_set("group:G_TEST_99", {
            "id": "G_TEST_99",
            "name": "Gruppo Studio",
            "creator": share_code,
            "members": [share_code, "ANOTHER_USER"]
        })
        redis_set(f"ratelimit:login:{clean_nick}", 4)

        # Execute cascade wipe
        result = cascade_wipe_account(clean_nick, share_code)
        self.assertTrue(result["ok"])
        self.assertTrue(result["wiped"])

        # Check account and share are removed
        self.assertIsNone(redis_get(f"account:{clean_nick}"))
        self.assertIsNone(redis_get(f"share:{share_lower}"))
        self.assertIsNone(redis_get(f"user_groups:{share_lower}"))
        self.assertIsNone(redis_get(f"ratelimit:login:{clean_nick}"))

        # Check user was removed from group members
        group_after = redis_get("group:G_TEST_99")
        self.assertIsNotNone(group_after)
        self.assertNotIn(share_code, group_after["members"])
        self.assertIn("ANOTHER_USER", group_after["members"])

    def test_cascade_wipe_deletes_sole_member_group(self):
        # If user is the only member, the group should be wiped entirely
        clean_nick = "test_gdpr_user"
        share_code = "TST999"
        share_lower = "tst999"

        redis_set(f"account:{clean_nick}", {"share_code": share_code})
        redis_set(f"share:{share_lower}", {"share_code": share_code})
        redis_set(f"user_groups:{share_lower}", ["G_TEST_99"])
        redis_set("group:G_TEST_99", {
            "id": "G_TEST_99",
            "name": "Gruppo Singolo",
            "creator": share_code,
            "members": [share_code]
        })

        cascade_wipe_account(clean_nick, share_code)
        self.assertIsNone(redis_get("group:G_TEST_99"))

    def test_gdpr_export_data(self):
        # Setup account & session
        clean_nick = "test_gdpr_user"
        share_code = "TST999"
        redis_set("session:test_gdpr_token", {"clean_nick": clean_nick, "share_code": share_code})
        redis_set(f"account:{clean_nick}", {
            "nickname": "Mario Rossi",
            "email": "m.rossi@campus.unimib.it",
            "role": "student",
            "auth_type": "google_campus",
            "share_code": share_code,
            "config": {"anno": "2024", "corso": "F1801D"},
            "exam_courses": ["F1801D-1"]
        })

        h = ProfileHandler.__new__(ProfileHandler)
        h.path = "/api/profile?export=1"
        h.headers = {"Authorization": "Bearer test_gdpr_token"}
        sent_status = None
        sent_body = None

        def mock_send(code, body):
            nonlocal sent_status, sent_body
            sent_status = code
            sent_body = body

        h._send_json = mock_send
        h.do_GET()

        self.assertEqual(sent_status, 200)
        self.assertTrue(sent_body.get("ok"))
        self.assertIn("Art. 20", sent_body.get("gdpr_compliance", ""))
        self.assertEqual(sent_body["user_profile"]["email"], "m.rossi@campus.unimib.it")
        self.assertEqual(sent_body["study_preferences"]["config"]["corso"], "F1801D")

    def test_gdpr_export_unauthorized(self):
        h = ProfileHandler.__new__(ProfileHandler)
        h.path = "/api/profile?export=1"
        h.headers = {}
        sent_status = None
        sent_body = None

        def mock_send(code, body):
            nonlocal sent_status, sent_body
            sent_status = code
            sent_body = body

        h._send_json = mock_send
        h.do_GET()

        self.assertEqual(sent_status, 401)

    def test_anonymize_nickname_put(self):
        clean_nick = "test_gdpr_user"
        share_code = "TST999"
        redis_set("session:test_gdpr_token", {"clean_nick": clean_nick, "share_code": share_code})
        redis_set(f"account:{clean_nick}", {
            "nickname": "Mario Rossi Reale",
            "email": "m.rossi@campus.unimib.it",
            "share_code": share_code
        })

        h = ProfileHandler.__new__(ProfileHandler)
        h.path = "/api/profile"
        h.headers = {"Authorization": "Bearer test_gdpr_token"}
        h._read_body = lambda: {"nickname": "Studente Anonimo 42"}

        sent_status = None
        sent_body = None

        def mock_send(code, body):
            nonlocal sent_status, sent_body
            sent_status = code
            sent_body = body

        h._send_json = mock_send
        h.do_PUT()

        self.assertEqual(sent_status, 200)
        self.assertEqual(sent_body.get("nickname"), "Studente Anonimo 42")

        acc = redis_get(f"account:{clean_nick}")
        self.assertEqual(acc.get("nickname"), "Studente Anonimo 42")

        share = redis_get("share:tst999")
        self.assertEqual(share.get("nickname"), "Studente Anonimo 42")

    def test_security_headers_and_csp_in_vercel_json(self):
        vjson_path = os.path.join(_root, "vercel.json")
        with open(vjson_path, "r", encoding="utf-8") as f:
            vjson = json.load(f)

        headers_map = {}
        for entry in vjson.get("headers", []):
            if entry.get("source") == "/(.*)":
                for h in entry.get("headers", []):
                    headers_map[h["key"]] = h["value"]

        self.assertIn("Content-Security-Policy", headers_map)
        self.assertIn("default-src 'self'", headers_map["Content-Security-Policy"])
        self.assertIn("font-src 'self' data:", headers_map["Content-Security-Policy"])
        self.assertNotIn("fonts.gstatic.com", headers_map["Content-Security-Policy"])
        self.assertIn("Cross-Origin-Opener-Policy", headers_map)
        self.assertEqual(headers_map["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")
        self.assertEqual(headers_map["X-Frame-Options"], "DENY")
        self.assertEqual(headers_map["X-Content-Type-Options"], "nosniff")

    def test_self_hosted_fonts_and_zero_google_fonts_network(self):
        # 1. Verify 6 font files exist in public/fonts
        fonts_dir = os.path.join(_root, "public", "fonts")
        self.assertTrue(os.path.isdir(fonts_dir))
        expected_fonts = [
            "pt-sans-v18-latin-regular-400.woff2",
            "pt-sans-v18-latin-bold-700.woff2",
            "pt-sans-v18-latin-italic-400.woff2",
            "pt-sans-v18-latin-italic-700.woff2",
            "pt-sans-narrow-v19-latin-regular-400.woff2",
            "pt-sans-narrow-v19-latin-bold-700.woff2",
        ]
        for f in expected_fonts:
            p = os.path.join(fonts_dir, f)
            self.assertTrue(os.path.isfile(p), f"Missing font file: {f}")
            self.assertGreater(os.path.getsize(p), 10000, f"Font file empty or corrupt: {f}")

        # 2. Verify style.css defines local @font-face rules
        style_path = os.path.join(_root, "public", "css", "style.css")
        with open(style_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn("@font-face", css)
        self.assertIn("/fonts/pt-sans-v18-latin-regular-400.woff2", css)
        self.assertIn("/fonts/pt-sans-narrow-v19-latin-regular-400.woff2", css)

        # 3. Verify index.html does NOT link to Google Fonts
        index_path = os.path.join(_root, "public", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)


if __name__ == '__main__':
    unittest.main()
