import sys
import os
import json
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from api._common import (
    BaseApiHandler,
    clean_html,
    redis_get,
    redis_set,
    redis_del,
    sanitize_text,
    get_authenticated_account,
)

INDEX_KEY = "teacher_notes:index"


def _get_notes_index() -> Dict[str, Any]:
    raw = redis_get(INDEX_KEY)
    if isinstance(raw, dict):
        return raw
    return {"courses": [], "lessons": []}


def _save_notes_index(idx: Dict[str, Any]) -> None:
    redis_set(INDEX_KEY, idx)


def get_all_notes_and_assignments() -> Dict[str, Any]:
    idx = _get_notes_index()
    course_notes = {}
    lesson_notes = {}
    lesson_teachers = {}
    all_notes = {}

    for c_code in idx.get("courses", []):
        c_clean = str(c_code).strip().upper()
        note_data = redis_get(f"course_note:{c_clean}")
        if note_data:
            course_notes[c_clean] = note_data
            all_notes[f"course_note:{c_clean}"] = note_data

    for l_id in idx.get("lessons", []):
        l_clean = str(l_id).strip()
        l_note = redis_get(f"lesson_note:{l_clean}")
        if l_note:
            lesson_notes[l_clean] = l_note
            all_notes[f"lesson_note:{l_clean}"] = l_note
        l_teacher = redis_get(f"lesson_teacher:{l_clean}")
        if l_teacher:
            lesson_teachers[l_clean] = l_teacher

    designated_teachers_simple = {
        k: (v.get("designated_teacher") if isinstance(v, dict) else v)
        for k, v in lesson_teachers.items()
    }

    return {
        "ok": True,
        "course_notes": course_notes,
        "lesson_notes": lesson_notes,
        "lesson_teachers": lesson_teachers,
        "notes": all_notes,
        "designated_teachers": designated_teachers_simple,
    }


class handler(BaseApiHandler):
    def do_OPTIONS(self):
        self.handle_options(methods="GET, POST, DELETE, OPTIONS", headers="Content-Type, Authorization")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        course_code = (qs.get("course", [""])[0] or "").strip().upper()
        lesson_id = (qs.get("lesson_id", [""])[0] or "").strip()

        # If single query
        if course_code and not qs.get("all"):
            note = redis_get(f"course_note:{course_code}")
            return self.send_json(200, {
                "ok": True,
                "course_code": course_code,
                "note": note
            }, cache_control='no-store')

        if lesson_id and not qs.get("all"):
            l_note = redis_get(f"lesson_note:{lesson_id}")
            l_teacher = redis_get(f"lesson_teacher:{lesson_id}")
            return self.send_json(200, {
                "ok": True,
                "lesson_id": lesson_id,
                "lesson_note": l_note,
                "designated_teacher": l_teacher
            }, cache_control='no-store')

        # Otherwise return all notes
        data = get_all_notes_and_assignments()
        return self.send_json(200, data, cache_control='no-store')

    def do_POST(self):
        body = self.read_json_body(max_bytes=65536)
        if not body or not isinstance(body, dict):
            return self.send_json(400, {"error": "Corpo della richiesta JSON non valido"}, cache_control='no-store')

        # ── Autenticazione & Autorizzazione Docente ───────────────────────────
        account, auth_err = get_authenticated_account(self.headers, body)
        if auth_err:
            return self.send_json(401, {"error": f"Autenticazione richiesta: {auth_err}"}, cache_control='no-store')

        if not account or account.get("role") != "professor":
            return self.send_json(403, {
                "error": "Accesso riservato esclusivamente ai docenti (@unimib.it). Gli studenti non possono modificare le note o assegnare docenti."
            }, cache_control='no-store')

        action = (body.get("action") or "set_note").strip()
        course_code = (body.get("course_code") or "").strip().upper()
        lesson_id = (body.get("lesson_id") or "").strip()
        author_name = sanitize_text(account.get("nickname") or body.get("author_name") or "Docente", max_len=80)
        author_email = sanitize_text(account.get("email") or body.get("author_email") or "", max_len=120)
        now_iso = datetime.now(timezone.utc).isoformat()

        idx = _get_notes_index()
        courses_set = set(idx.get("courses", []))
        lessons_set = set(idx.get("lessons", []))

        if action == "set_note":
            raw_note = body.get("note") or ""
            note_text = clean_html(raw_note)[:1000]
            if not course_code and not lesson_id:
                return self.send_json(400, {"error": "Specificare 'course_code' o 'lesson_id' per salvare la nota"}, cache_control='no-store')
            if not note_text:
                return self.send_json(400, {"error": "Testo della nota obbligatorio"}, cache_control='no-store')

            payload = {
                "note": note_text,
                "author_name": author_name,
                "author_email": author_email,
                "updated_at": now_iso,
                "course_code": course_code,
                "lesson_id": lesson_id,
            }

            if lesson_id:
                redis_set(f"lesson_note:{lesson_id}", payload)
                lessons_set.add(lesson_id)
            if course_code:
                redis_set(f"course_note:{course_code}", payload)
                courses_set.add(course_code)

            idx["courses"] = sorted(list(courses_set))
            idx["lessons"] = sorted(list(lessons_set))
            _save_notes_index(idx)

            return self.send_json(200, {
                "ok": True,
                "action": "set_note",
                "saved": payload
            }, cache_control='no-store')

        elif action == "set_designated_teacher":
            teacher = sanitize_text(body.get("designated_teacher") or body.get("teacher_name") or "", max_len=100)
            if not lesson_id:
                return self.send_json(400, {"error": "Parametro 'lesson_id' obbligatorio per assegnare il docente"}, cache_control='no-store')

            payload = {
                "lesson_id": lesson_id,
                "course_code": course_code,
                "designated_teacher": teacher,
                "author_name": author_name,
                "author_email": author_email,
                "updated_at": now_iso,
            }

            redis_set(f"lesson_teacher:{lesson_id}", payload)
            lessons_set.add(lesson_id)
            if course_code:
                courses_set.add(course_code)

            idx["courses"] = sorted(list(courses_set))
            idx["lessons"] = sorted(list(lessons_set))
            _save_notes_index(idx)

            return self.send_json(200, {
                "ok": True,
                "action": "set_designated_teacher",
                "saved": payload
            }, cache_control='no-store')

        elif action == "delete_note":
            if not course_code and not lesson_id:
                return self.send_json(400, {"error": "Specificare 'course_code' o 'lesson_id' per eliminare la nota"}, cache_control='no-store')
            if lesson_id:
                redis_del(f"lesson_note:{lesson_id}")
            if course_code:
                redis_del(f"course_note:{course_code}")

            return self.send_json(200, {"ok": True, "deleted": True}, cache_control='no-store')

        return self.send_json(400, {"error": f"Azione '{action}' non supportata"}, cache_control='no-store')
