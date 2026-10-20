"""
Tests for Google OAuth 2.0 (Students @campus.unimib.it and Professors @unimib.it),
Persistent 365-day Sessions, and GDPR Account Deletion.
"""

import unittest
import os
import sys
import io
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.profile as profile_mod


def _make_handler(method: str, path: str, body: dict = None, headers: dict = None):
    h = profile_mod.handler.__new__(profile_mod.handler)
    h.path = path
    h.headers = headers or {}
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    h.headers["Content-Length"] = str(len(payload))
    h.rfile = io.BytesIO(payload)
    h.wfile = io.BytesIO()

    status_code = None

    def fake_send_response(code):
        nonlocal status_code
        status_code = code

    h.send_response = fake_send_response
    h.send_header = lambda *a: None
    h.end_headers = lambda: None

    def execute():
        getattr(h, f"do_{method}")()
        raw = h.wfile.getvalue()
        data = json.loads(raw.decode("utf-8")) if raw else {}
        return status_code, data

    return execute


class TestGoogleAuthAndGdpr(unittest.TestCase):

    def setUp(self):
        # Reset local store
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

    def test_verify_google_token_domain_restriction(self):
        """Strict domain check: only @campus.unimib.it and @unimib.it are allowed."""
        # External domains rejected
        claims, err = profile_mod._verify_google_token("mock_google_token:utente@gmail.com:sub123:Mario")
        self.assertIsNone(claims)
        self.assertIn("campus.unimib.it", err)

        claims, err = profile_mod._verify_google_token("mock_google_token:utente@unimi.it:sub123:Mario")
        self.assertIsNone(claims)
        self.assertIn("unimib.it", err)

        # Student email (@campus.unimib.it) -> role: student
        claims, err = profile_mod._verify_google_token("mock_google_token:m.rossi@campus.unimib.it:sub_stud:Mario Rossi")
        self.assertIsNone(err)
        self.assertIsNotNone(claims)
        self.assertEqual(claims["email"], "m.rossi@campus.unimib.it")
        self.assertEqual(claims["role"], "student")

        # Student with duplicate number (e.g. m.rossi2@campus.unimib.it) -> role: student
        claims, err = profile_mod._verify_google_token("mock_google_token:m.rossi2@campus.unimib.it:sub_stud2:Mario Rossi")
        self.assertIsNone(err)
        self.assertEqual(claims["role"], "student")

        # Professor email (@unimib.it) -> role: professor
        claims, err = profile_mod._verify_google_token("mock_google_token:mario.rossi@unimib.it:sub_prof:Prof. Mario Rossi")
        self.assertIsNone(err)
        self.assertIsNotNone(claims)
        self.assertEqual(claims["email"], "mario.rossi@unimib.it")
        self.assertEqual(claims["role"], "professor")

    def test_google_auth_endpoint_and_session_ttl(self):
        """Test POST /api/profile creates student or professor profile with 365-day persistent session."""
        self.assertEqual(profile_mod.SESSION_TTL_SECONDS, 365 * 86400)

        # Non-unimib email attempt -> 403 Forbidden
        exec_rej = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:hacker@external.com:sub999:Hacker"
        })
        status, data = exec_rej()
        self.assertEqual(status, 403)
        self.assertIn("unimib.it", data["error"])

        # Student login -> 200 OK + role student
        exec_stud = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:m.rossi@campus.unimib.it:sub_stud_42:Mario Rossi",
            "config": {"corso": "F1801Q", "corsoLabel": "Informatica"}
        })
        status, resp_stud = exec_stud()
        self.assertEqual(status, 200)
        self.assertTrue(resp_stud["ok"])
        self.assertEqual(resp_stud["email"], "m.rossi@campus.unimib.it")
        self.assertEqual(resp_stud["role"], "student")
        stud_token = resp_stud["session_token"]

        # Professor login -> 200 OK + role professor
        exec_prof = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:mario.rossi@unimib.it:sub_prof_42:Prof. Mario Rossi"
        })
        status, resp_prof = exec_prof()
        self.assertEqual(status, 200)
        self.assertTrue(resp_prof["ok"])
        self.assertEqual(resp_prof["email"], "mario.rossi@unimib.it")
        self.assertEqual(resp_prof["role"], "professor")
        prof_token = resp_prof["session_token"]

        # GET /api/profile?me=1 for student
        exec_me_stud = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {stud_token}"})
        status, me_stud = exec_me_stud()
        self.assertEqual(status, 200)
        self.assertEqual(me_stud["role"], "student")

        # GET /api/profile?me=1 for professor
        exec_me_prof = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {prof_token}"})
        status, me_prof = exec_me_prof()
        self.assertEqual(status, 200)
        self.assertEqual(me_prof["role"], "professor")

    def test_auth_config_endpoint(self):
        """GET /api/profile?auth_config=1 returns configuration, allowed domains and disclaimer."""
        exec_cfg = _make_handler("GET", "/api/profile?auth_config=1")
        status, data = exec_cfg()
        self.assertEqual(status, 200)
        self.assertIn("campus.unimib.it", data["allowed_domains"])
        self.assertIn("unimib.it", data["allowed_domains"])
        self.assertIn("studentesco", data["disclaimer"])

    def test_multiple_accounts_coexistence_and_switching(self):
        """Verify that multiple accounts (e.g. Student and Professor) have distinct sessions and configs that do not leak."""
        # 1. Login Account A (Student)
        exec_stud = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:m.rossi@campus.unimib.it:sub_student_1:Mario Rossi",
            "config": {"corso": "F1801Q", "corsoLabel": "Informatica"}
        })
        status, data_stud = exec_stud()
        self.assertEqual(status, 200)
        token_stud = data_stud["session_token"]
        self.assertEqual(data_stud["role"], "student")

        # 2. Login Account B (Professor)
        exec_prof = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:mario.rossi@unimib.it:sub_prof_1:Prof. Mario Rossi",
            "config": {"corso": "DOC_INF", "corsoLabel": "Cattedra Informatica"}
        })
        status, data_prof = exec_prof()
        self.assertEqual(status, 200)
        token_prof = data_prof["session_token"]
        self.assertEqual(data_prof["role"], "professor")

        # 3. Verify Account Switching via Bearer token: Account A
        exec_me_stud = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {token_stud}"})
        status, me_stud = exec_me_stud()
        self.assertEqual(status, 200)
        self.assertEqual(me_stud["email"], "m.rossi@campus.unimib.it")
        self.assertEqual(me_stud["role"], "student")
        self.assertEqual(me_stud["config"]["corso"], "F1801Q")

        # 4. Verify Account Switching via Bearer token: Account B
        exec_me_prof = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {token_prof}"})
        status, me_prof = exec_me_prof()
        self.assertEqual(status, 200)
        self.assertEqual(me_prof["email"], "mario.rossi@unimib.it")
        self.assertEqual(me_prof["role"], "professor")
        self.assertEqual(me_prof["config"]["corso"], "DOC_INF")

        # 5. Logout Account A: should invalidate only Account A's token
        exec_del_stud = _make_handler("DELETE", "/api/profile", headers={"Authorization": f"Bearer {token_stud}"})
        status, del_resp = exec_del_stud()
        self.assertEqual(status, 200)

        # Token A is invalid
        exec_me_stud_after = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {token_stud}"})
        status, _ = exec_me_stud_after()
        self.assertEqual(status, 401)

        # Token B remains fully valid
        exec_me_prof_after = _make_handler("GET", "/api/profile?me=1", headers={"Authorization": f"Bearer {token_prof}"})
        status, me_prof_after = exec_me_prof_after()
        self.assertEqual(status, 200)
        self.assertEqual(me_prof_after["role"], "professor")

    def test_gdpr_account_wipe(self):
        """DELETE /api/profile?wipe=1 purges account, share code, and session for any role (GDPR Art. 17)."""
        # Create Professor account
        exec_post = _make_handler("POST", "/api/profile", {
            "action": "google",
            "credential": "mock_google_token:prof.wipe@unimib.it:sub_wipe_prof:Prof. Wipe"
        })
        status, data = exec_post()
        self.assertEqual(status, 200)
        session_token = data["session_token"]
        share_code = data["share_code"]

        # Ensure account exists in store
        self.assertIsNotNone(profile_mod.redis_get("account:google:sub_wipe_prof"))
        self.assertIsNotNone(profile_mod.redis_get(f"share:{share_code.lower()}"))

        # Issue GDPR wipe request
        exec_del = _make_handler("DELETE", "/api/profile?wipe=1", headers={"Authorization": f"Bearer {session_token}"})
        status, del_data = exec_del()
        self.assertEqual(status, 200)

        # Verify completely deleted from storage
        self.assertIsNone(profile_mod.redis_get("account:google:sub_wipe_prof"))
        self.assertIsNone(profile_mod.redis_get(f"share:{share_code.lower()}"))
        self.assertIsNone(profile_mod._get_session(session_token))


if __name__ == "__main__":
    unittest.main()
