"""
Comprehensive Unit & Integration Test Suite for UNIMIB Calendar API
Tests all 9 modules in api/:
- api/options.py
- api/calendar.py
- api/rooms.py
- api/exams.py
- api/teachers.py
- api/export.py
- api/shared_calendar.py
- api/group.py
- api/profile.py
"""

import unittest
import os
import sys
import io
import json
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.options as options_mod
import api.calendar as calendar_mod
import api.rooms as rooms_mod
import api.exams as exams_mod
import api.teachers as teachers_mod
import api.export as export_mod
import api.shared_calendar as shared_calendar_mod
import api.group as group_mod
import api.profile as profile_mod


class BaseHandlerTest(unittest.TestCase):
    """Helper class to instantiate and execute BaseHTTPRequestHandler methods with mocked IO."""

    def invoke_handler(self, handler_cls, method, path="/", body=None, headers=None):
        h = handler_cls.__new__(handler_cls)
        h.path = path
        h.command = method
        h.headers = dict(headers or {})
        
        body_bytes = b""
        if body is not None:
            if isinstance(body, dict):
                body_bytes = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body_bytes = body.encode("utf-8")
            elif isinstance(body, bytes):
                body_bytes = body
            h.headers["Content-Length"] = str(len(body_bytes))
        else:
            h.headers.setdefault("Content-Length", "0")

        h.rfile = io.BytesIO(body_bytes)
        h.wfile = io.BytesIO()

        self.sent_status = None
        self.sent_headers = {}

        def fake_send_response(code):
            self.sent_status = code

        def fake_send_header(k, v):
            self.sent_headers[k] = v

        h.send_response = fake_send_response
        h.send_header = fake_send_header
        h.end_headers = lambda: None

        func = getattr(h, f"do_{method}")
        func()

        raw_output = h.wfile.getvalue()
        json_output = None
        try:
            json_output = json.loads(raw_output.decode("utf-8", errors="replace"))
        except Exception:
            pass

        return self.sent_status, self.sent_headers, raw_output, json_output


class TestOptionsModule(BaseHandlerTest):
    def setUp(self):
        options_mod._cache.clear()

    def test_study_year_number(self):
        self.assertEqual(options_mod.study_year_number("GGG|2"), "2")
        self.assertEqual(options_mod.study_year_number("F0602Q-001|1"), "1")
        self.assertEqual(options_mod.study_year_number("T1 - Monza|3"), "3")
        self.assertEqual(options_mod.study_year_number("NoPipe"), "NoPipe")

    def test_js_var_extraction(self):
        script = 'var elenco_corsi = [{"valore":"F1801Q","label":"Informatica"}];\nvar test_num = 42;'
        self.assertEqual(options_mod.js_var(script, "elenco_corsi"), [{"valore":"F1801Q","label":"Informatica"}])
        self.assertEqual(options_mod.js_var(script, "test_num"), 42)
        self.assertIsNone(options_mod.js_var(script, "non_existent"))

    @patch("api.options.fetch_combo")
    def test_get_academic_years(self, mock_combo):
        mock_combo.return_value = 'var anni_accademici_ec = [{"valore":"2026","label":"2025/2026"},{"valore":"2025","label":"2024/2025"}];'
        years = options_mod.get_academic_years()
        self.assertEqual(len(years), 2)
        self.assertEqual(years[0]["value"], "2026")

    @patch("api.options.get_courses_data")
    def test_get_areas_and_courses(self, mock_courses_data):
        mock_courses_data.return_value = (
            [
                {
                    "valore": "F1801Q",
                    "label": "Informatica",
                    "tipo": "Laurea",
                    "scuola": "scuola_scienze",
                    "elenco_anni": [{"valore": "GGG|1", "label": "1° Anno"}]
                },
                {
                    "valore": "OTHER",
                    "label": "Altro Corso",
                    "tipo": "Master",
                    "scuola": None,
                    "elenco_anni": [{"valore": "GGG|0", "label": "Anno Zero"}, {"valore": "GGG|1", "label": "1° Anno"}]
                }
            ],
            [{"valore": "scuola_scienze", "label": "Scienze"}]
        )
        res = options_mod.get_areas_and_courses("2026")
        self.assertIn("areas", res)
        self.assertIn("courses", res)
        # Check 'altri_corsi' added because scuola was None
        area_values = [a["value"] for a in res["areas"]]
        self.assertIn("altri_corsi", area_values)
        # Check year 0 was filtered out
        other_course = next(c for c in res["courses"] if c["value"] == "OTHER")
        self.assertEqual(len(other_course["years"]), 1)
        self.assertEqual(other_course["years"][0]["year"], "1")

    @patch("api.options.get_courses_data")
    def test_get_course_teachings(self, mock_courses_data):
        mock_courses_data.return_value = (
            [
                {
                    "valore": "F1801Q",
                    "label": "Informatica",
                    "elenco_anni": [
                        {
                            "valore": "GGG|1",
                            "label": "1° Anno",
                            "elenco_insegnamenti": [
                                {"valore": "INF101", "label": "Programmazione 1", "docente": "Rossi"}
                            ]
                        }
                    ]
                }
            ],
            []
        )
        teachings = options_mod.get_course_teachings("2026", "F1801Q")
        self.assertIsNotNone(teachings)
        self.assertEqual(teachings["label"], "Informatica")
        self.assertEqual(len(teachings["years"][0]["teachings"]), 1)
        self.assertEqual(teachings["years"][0]["teachings"][0]["code"], "INF101")

        # Not found
        self.assertIsNone(options_mod.get_course_teachings("2026", "NON_EXISTENT"))

    @patch("api.options.get_academic_years")
    def test_handler_do_get_academic_years(self, mock_years):
        mock_years.return_value = [{"value": "2026", "label": "2025/2026"}]
        status, headers, raw, payload = self.invoke_handler(options_mod.handler, "GET", "/api/options")
        self.assertEqual(status, 200)
        self.assertIn("academic_years", payload)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_handler_do_get_validation_errors(self):
        status, _, _, payload = self.invoke_handler(options_mod.handler, "GET", "/api/options?anno=invalid")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

        status, _, _, payload = self.invoke_handler(options_mod.handler, "GET", "/api/options?anno=2026&corso=bad%20chars!")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


class TestCalendarModule(BaseHandlerTest):
    def setUp(self):
        calendar_mod._grid_cache.clear()

    def test_get_monday(self):
        from datetime import datetime
        # Wednesday
        wed = datetime(2026, 10, 7)
        mon = calendar_mod.get_monday(wed)
        self.assertEqual(mon.strftime("%d-%m-%Y"), "05-10-2026")

    def test_split_curricula(self):
        raw = "Curriculum 1<hr>Curriculum 2<b>bold</b><hr>"
        parts = calendar_mod.split_curricula(raw)
        self.assertEqual(parts, ["Curriculum 1", "Curriculum 2bold"])
        self.assertEqual(calendar_mod.split_curricula(None), [])

    @patch("urllib.request.urlopen")
    def test_fetch_unimib_grid_and_caching(self, mock_urlopen):
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"first_day_label": "05-10-2026", "celle": []}).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        mock_urlopen.return_value = fake_response

        data1 = calendar_mod.fetch_unimib_grid("2026", "F1801Q", ["GGG|1"], "05-10-2026")
        self.assertEqual(data1["first_day_label"], "05-10-2026")
        self.assertEqual(mock_urlopen.call_count, 1)

        # Cache hit
        data2 = calendar_mod.fetch_unimib_grid("2026", "F1801Q", ["GGG|1"], "05-10-2026")
        self.assertEqual(data2["first_day_label"], "05-10-2026")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("api.calendar.fetch_unimib_grid")
    def test_handler_do_get_success_and_cancellation(self, mock_fetch):
        mock_fetch.return_value = {
            "first_day_label": "05-10-2026",
            "last_day_label": "09-10-2026",
            "giorni": [{"data": "05-10-2026"}],
            "celle": [
                {
                    "timestamp": 1728200000,
                    "id": "ev_1",
                    "nome_insegnamento": "Programmazione 1",
                    "codice_insegnamento": "INF101",
                    "data": "05-10-2026",
                    "nome_giorno": "Lunedì",
                    "ora_inizio": "08:30",
                    "ora_fine": "10:30",
                    "docente": "Mario Rossi",
                    "aula": "U1-01",
                    "Annullato": "1"
                }
            ]
        }

        path = "/api/calendar?anno=2026&corso=F1801Q&anno2=GGG|1&date=05-10-2026"
        status, headers, _, payload = self.invoke_handler(calendar_mod.handler, "GET", path)
        self.assertEqual(status, 200)
        self.assertEqual(payload["total_events"], 1)
        ev = payload["events"][0]
        self.assertEqual(ev["course"], "Programmazione 1")
        self.assertTrue(ev["is_canceled"])
        self.assertFalse(ev["is_external"])

    def test_handler_validation(self):
        # Missing required parameters
        status, _, _, payload = self.invoke_handler(calendar_mod.handler, "GET", "/api/calendar?anno=2026")
        self.assertEqual(status, 400)

        # Invalid date format
        status, _, _, payload = self.invoke_handler(calendar_mod.handler, "GET", "/api/calendar?anno=2026&corso=F1801Q&anno2=GGG|1&date=2026/10/05")
        self.assertEqual(status, 400)


class TestRoomsModule(BaseHandlerTest):
    def setUp(self):
        rooms_mod._cache.clear()

    def test_time_parsing_and_formatting(self):
        self.assertEqual(rooms_mod.parse_time_str("08:30:00"), 510)
        self.assertEqual(rooms_mod.parse_time_str("14:15"), 855)
        self.assertEqual(rooms_mod.parse_time_str(""), 0)
        self.assertEqual(rooms_mod.format_minutes(510), "08:30")
        self.assertEqual(rooms_mod.format_minutes(855), "14:15")

    @patch("api.rooms.fetch_json")
    def test_room_occupancy_contiguous_events(self, mock_fetch):
        # Mock rooms_call.php response with two contiguous events
        mock_fetch.return_value = {
            "all_rooms": {
                "U1-01": {"room_name": "Aula U1-01", "capacity": 120}
            },
            "events": [
                {
                    "CodiceAula": "U1-01",
                    "name": "Lezione 1",
                    "from": "08:30:00",
                    "to": "10:30:00",
                    "Annullato": "0"
                },
                {
                    "CodiceAula": "U1-01",
                    "name": "Lezione 2",
                    "from": "10:30:00",
                    "to": "12:30:00",
                    "Annullato": "0"
                }
            ]
        }

        # Check at 09:00 (during Lezione 1) -> should chain until 12:30
        res = rooms_mod.get_room_occupancy("U1", "05-10-2026", time_str="09:00")
        self.assertEqual(res["total_rooms"], 1)
        r = res["rooms"][0]
        self.assertFalse(r["is_free"])
        self.assertEqual(r["occupied_from"], "08:30")
        self.assertEqual(r["occupied_until"], "12:30")
        self.assertEqual(r["chained_next_event"]["name"], "Lezione 2")

    @patch("api.rooms.get_buildings")
    def test_handler_get_buildings(self, mock_bld):
        mock_bld.return_value = [{"value": "U1", "label": "Edificio U1"}]
        status, _, _, payload = self.invoke_handler(rooms_mod.handler, "GET", "/api/rooms")
        self.assertEqual(status, 200)
        self.assertEqual(payload["buildings"], [{"value": "U1", "label": "Edificio U1"}])

    def test_handler_validation(self):
        status, _, _, payload = self.invoke_handler(rooms_mod.handler, "GET", "/api/rooms?sede=U1&time=invalid_time")
        self.assertEqual(status, 400)


class TestExamsModule(BaseHandlerTest):
    def setUp(self):
        exams_mod._cache.clear()

    def test_parse_exam_event(self):
        ev = {
            "id": "12345",
            "name": "ALGORITMI E STRUTTURE DATI",
            "description": "Corso di laurea: Informatica [E3101Q] 2 anno // Curriculum Generale\nNumero appello: 2",
            "Utenti": [{"Cognome": "Rossi", "Nome": "Mario"}],
            "Giorno": "2026-06-15",
            "from": "09:00:00",
            "to": "12:00:00",
            "NomeAula": "U1-01",
            "NomeSede": "Edificio U1",
            "Annullato": "0"
        }
        parsed = exams_mod.parse_exam_event(ev)
        self.assertEqual(parsed["name"], "ALGORITMI E STRUTTURE DATI")
        self.assertEqual(parsed["appello"], "2")
        self.assertEqual(parsed["day_name"], "Lunedì")
        self.assertEqual(parsed["date_formatted"], "15/06/2026")
        self.assertEqual(len(parsed["courses"]), 1)
        self.assertEqual(parsed["courses"][0]["code"], "E3101Q")
        self.assertEqual(parsed["courses"][0]["year"], "2")
        self.assertEqual(parsed["docenti"], ["Rossi Mario"])

    @patch("api.exams.fetch_json")
    def test_get_exams_filtering(self, mock_fetch):
        mock_fetch.return_value = {
            "events": [
                {
                    "id": "1",
                    "name": "ANALISI MATEMATICA",
                    "description": "Corso di laurea: Informatica [E3101Q] 1 anno",
                    "Giorno": "2026-06-10",
                    "from": "09:00:00",
                    "to": "11:00:00",
                    "Annullato": "0"
                },
                {
                    "id": "2",
                    "name": "FISICA",
                    "description": "Corso di laurea: Fisica [F1701Q] 1 anno",
                    "Giorno": "2026-06-12",
                    "from": "14:00:00",
                    "to": "16:00:00",
                    "Annullato": "0"
                }
            ]
        }

        # Filter by course E3101Q
        res = exams_mod.get_exams(corsi=["E3101Q"], datefrom="01-06-2026", dateto="30-06-2026")
        self.assertEqual(res["total_exams"], 1)
        self.assertEqual(res["exams"][0]["name"], "ANALISI MATEMATICA")

        # Filter by search term
        res_search = exams_mod.get_exams(search="fisica", datefrom="01-06-2026", dateto="30-06-2026")
        self.assertEqual(res_search["total_exams"], 1)
        self.assertEqual(res_search["exams"][0]["name"], "FISICA")

    def test_handler_validation(self):
        status, _, _, payload = self.invoke_handler(exams_mod.handler, "GET", "/api/exams?datefrom=invalid-date")
        self.assertEqual(status, 400)


class TestTeachersModule(BaseHandlerTest):
    def setUp(self):
        teachers_mod._cache.clear()

    def test_clean_html_and_extract_emails(self):
        self.assertEqual(teachers_mod.clean_html("<p>Prof. <b>Verdi</b></p>"), "Prof. Verdi")
        emails = teachers_mod.extract_emails("Contatto: prof.verdi@unimib.it e mario.rossi@unimib.it")
        self.assertEqual(emails, ["prof.verdi@unimib.it", "mario.rossi@unimib.it"])

    @patch("api.teachers.get_teachers_list")
    def test_handler_teachers_search(self, mock_list):
        mock_list.return_value = [
            {"code": "D1", "name": "Abbotto Alessandro", "courses": []},
            {"code": "D2", "name": "Rossi Mario", "courses": [{"code": "INF101", "name": "Programmazione"}]}
        ]
        status, _, _, payload = self.invoke_handler(teachers_mod.handler, "GET", "/api/teachers?anno=2026&q=rossi")
        self.assertEqual(status, 200)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["teachers"][0]["name"], "Rossi Mario")


class TestExportModule(BaseHandlerTest):
    def setUp(self):
        export_mod._grid_cache.clear()

    def test_date_and_ical_formatting(self):
        self.assertEqual(export_mod._format_ical_date("05-10-2026", "08:30"), "20261005T083000")
        self.assertEqual(export_mod._format_csv_date("05-10-2026"), "2026-10-05")
        self.assertEqual(export_mod._escape_ical("Lezione, Teoria; U1\nNote"), "Lezione\\, Teoria\\; U1\\nNote")

    @patch("api.export._fetch_unimib_grid")
    def test_handler_export_ics_and_csv_and_json(self, mock_grid):
        mock_grid.return_value = [
            {
                "id": "1",
                "nome_insegnamento": "Informatica Forense",
                "codice_insegnamento": "F1801Q",
                "data": "05-10-2026",
                "ora_inizio": "08:30",
                "ora_fine": "10:30",
                "docente": "Bianchi Luca",
                "aula": "U1-02",
                "tipo": "Lezione",
                "Annullato": "0"
            }
        ]

        # 1. ICS format
        status, headers, raw, _ = self.invoke_handler(
            export_mod.handler, "GET", "/api/export?anno=2026&corso=F1801Q&anno2=GGG|1&format=ics&weeks=1"
        )
        self.assertEqual(status, 200)
        self.assertIn("text/calendar", headers["Content-Type"])
        self.assertIn(b"BEGIN:VCALENDAR", raw)
        self.assertIn(b"SUMMARY:Informatica Forense", raw)

        # 2. CSV format
        status, headers, raw, _ = self.invoke_handler(
            export_mod.handler, "GET", "/api/export?anno=2026&corso=F1801Q&anno2=GGG|1&format=csv&weeks=1"
        )
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))  # UTF-8 BOM
        self.assertIn(b"Informatica Forense", raw)

        # 3. JSON format
        status, headers, _, payload = self.invoke_handler(
            export_mod.handler, "GET", "/api/export?anno=2026&corso=F1801Q&anno2=GGG|1&format=json&weeks=1"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["total_events"], 1)


class TestSharedCalendarModule(BaseHandlerTest):
    def setUp(self):
        shared_calendar_mod._grid_cache.clear()

    def test_options_preflight(self):
        status, headers, _, _ = self.invoke_handler(shared_calendar_mod.handler, "OPTIONS", "/api/shared_calendar")
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    @patch("api.shared_calendar._resolve_profile")
    @patch("api.shared_calendar._fetch_raw_grid")
    def test_shared_calendar_success(self, mock_fetch, mock_resolve):
        mock_resolve.return_value = (
            "k9x2p4",
            {
                "share_code": "K9X2P4",
                "nickname": "Marco",
                "config": {"anno": "2026", "corso": "F1801Q", "anni": ["1"]}
            }
        )
        mock_fetch.return_value = [
            {
                "data": "05-10-2026",
                "nome_giorno": "Lunedì",
                "ora_inizio": "09:00",
                "ora_fine": "11:00",
                "nome_insegnamento": "Algebra Lineare",
                "codice_insegnamento": "ALG1",
                "aula": "U1-03",
                "docente": "Prof. Neri",
                "Annullato": "0"
            }
        ]

        status, _, _, payload = self.invoke_handler(
            shared_calendar_mod.handler, "GET", "/api/shared_calendar?codes=k9x2p4&date=05-10-2026"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["profiles"]), 1)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0]["nickname"], "Marco")


class TestGroupAndProfileModules(BaseHandlerTest):
    def setUp(self):
        # Clear mock storage
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

    def test_profile_and_group_full_lifecycle(self):
        # 1. Register User A
        status, _, _, res_a = self.invoke_handler(
            profile_mod.handler, "POST", "/api/profile",
            body={"nickname": "Alice", "pin": "1234", "config": {"corso": "F1801Q"}}
        )
        self.assertEqual(status, 201)
        token_a = res_a["session_token"]
        share_a = res_a["share_code"]
        rec_a = res_a["recovery_code"]

        # 2. Register User B
        status, _, _, res_b = self.invoke_handler(
            profile_mod.handler, "POST", "/api/profile",
            body={"nickname": "Bob", "pin": "5678", "config": {"corso": "F1801Q"}}
        )
        self.assertEqual(status, 201)
        token_b = res_b["session_token"]
        share_b = res_b["share_code"]

        # 3. User A creates group
        status, _, _, grp_res = self.invoke_handler(
            group_mod.handler, "POST", "/api/group",
            body={"action": "create_group", "name": "Studio Insieme"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(status, 201)
        gid = grp_res["group"]["id"]
        self.assertEqual(grp_res["group"]["creator"], share_a)

        # 4. User A adds User B to group
        status, _, _, add_res = self.invoke_handler(
            group_mod.handler, "POST", "/api/group",
            body={"action": "add_member", "group_id": gid, "friend_code": share_b},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(add_res["members"]), 2)

        # 5. User B renames group
        status, _, _, ren_res = self.invoke_handler(
            group_mod.handler, "POST", "/api/group",
            body={"action": "rename_group", "group_id": gid, "name": "Studio Algoritmi"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(ren_res["group"]["name"], "Studio Algoritmi")

        # 6. User B leaves group
        status, _, _, leave_res = self.invoke_handler(
            group_mod.handler, "POST", "/api/group",
            body={"action": "leave_group", "group_id": gid},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(status, 200)

        # 7. Reset PIN with recovery code for User A
        status, _, _, rec_res = self.invoke_handler(
            profile_mod.handler, "POST", "/api/profile",
            body={"action": "reset_pin", "nickname": "Alice", "recovery_code": rec_a, "new_pin": "9999"}
        )
        self.assertEqual(status, 200)

        # 8. Login with new PIN
        status, _, _, login_res = self.invoke_handler(
            profile_mod.handler, "PUT", "/api/profile",
            body={"nickname": "Alice", "pin": "9999"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(login_res["share_code"], share_a)

        # 9. Logout
        status, _, _, _ = self.invoke_handler(
            profile_mod.handler, "DELETE", "/api/profile",
            headers={"Authorization": f"Bearer {login_res['session_token']}"}
        )
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
