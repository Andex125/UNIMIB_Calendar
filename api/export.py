import sys
import os
import json
import csv
import io
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
import concurrent.futures

_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from api._common import (
    BaseApiHandler,
    BoundedTTLCache,
    get_rome_now,
    get_monday,
    parse_date_to_monday,
    safe_ts,
    fetch_upstream,
    UpstreamError,
    redis_get,
)

GRID_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/grid_call.php'
CACHE_TTL = 300

_grid_cache = BoundedTTLCache(maxsize=200, ttl_seconds=CACHE_TTL)

_get_monday = get_monday
_safe_ts = safe_ts
_redis_get = redis_get


def _parse_date_to_monday(date_str: str) -> datetime:
    if not date_str:
        return get_monday()
    clean = str(date_str).strip().replace('/', '-')
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(clean, fmt)
            return get_monday(dt)
        except ValueError:
            pass
    return get_monday()


def _fetch_unimib_grid(anno: str, corso: str, anni_tuple: tuple, monday_str: str) -> list:
    if not anno or not corso or not anni_tuple:
        return []

    cache_key = (anno, corso, anni_tuple, monday_str)
    cached = _grid_cache.get(cache_key)
    if cached is not None:
        return cached

    params = [
        ("view", "easycourse"),
        ("form-type", "corso"),
        ("include", "corso"),
        ("anno", anno),
        ("corso", corso),
        *[("anno2[]", a) for a in anni_tuple],
        ("date", monday_str),
        ("_lang", "it"),
    ]
    url = f"{GRID_URL}?{urllib.parse.urlencode(params)}"
    try:
        raw_text = fetch_upstream(url, timeout=12)
        raw_data = json.loads(raw_text)
        if isinstance(raw_data, dict):
            cells = sorted(raw_data.get("celle", []), key=safe_ts)
            _grid_cache.set(cache_key, cells)
            return cells
    except Exception:
        pass
    return []


def _escape_ical(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("\r\n", "\n").replace("\r", "\n").replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


def _fold_ical_line(line: str) -> str:
    """RFC 5545 section 3.1: lines of text SHOULD NOT be longer than 75 octets."""
    encoded = line.encode('utf-8')
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        cut = 75
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode('utf-8'))
        encoded = b' ' + encoded[cut:]
    parts.append(encoded.decode('utf-8'))
    return "\r\n".join(parts)


def _format_ical_date(day_date: str, time_str: str) -> str:
    clean = (day_date or "").strip().replace("/", "-")
    parts = clean.split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            d_clean = f"{parts[0]}{parts[1]}{parts[2]}"
        else:
            d_clean = f"{parts[2]}{parts[1]}{parts[0]}"
    else:
        d_clean = get_rome_now().strftime("%Y%m%d")
    t_clean = (time_str or "09:00").replace(":", "")
    if len(t_clean) == 4:
        t_clean += "00"
    return f"{d_clean}T{t_clean}"


def _format_csv_date(day_date: str) -> str:
    clean = (day_date or "").strip().replace("/", "-")
    parts = clean.split("-")
    if len(parts) == 3:
        if len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        elif len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1]}-{parts[2]}"
    return clean


def _sanitize_csv_cell(val: Any) -> str:
    """Neutralize spreadsheet formula injection (CWE-1236)."""
    s = str(val if val is not None else "")
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


class handler(BaseApiHandler):

    def _qs(self) -> dict:
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query)

    def do_OPTIONS(self):
        self.handle_options(methods="GET, OPTIONS", headers="Content-Type")

    def do_GET(self):
        qs = self._qs()

        # 1. Resolve Profile or Query Parameters
        code = qs.get("code", [""])[0].strip().lower()
        cfg = None
        cal_name = "Orario UNIMIB"

        if code:
            prof = _redis_get(f"share:{code}") or _redis_get(f"account:{code}") or _redis_get(f"profile:{code}")
            if prof and isinstance(prof, dict):
                cfg = prof.get("config")
                nick = prof.get("nickname")
                if nick:
                    cal_name = f"Orario UNIMIB - {nick}"

        if not cfg:
            anno = qs.get("anno", [""])[0].strip()
            corso = qs.get("corso", [""])[0].strip()
            anni = [a for a in qs.get("anno2", []) if a]
            fav_str = qs.get("fav", [""])[0].strip()
            fav_codes = [f.strip() for f in fav_str.split(",") if f.strip()] if fav_str else []

            if anno and corso and anni:
                cfg = {
                    "anno": anno,
                    "corso": corso,
                    "anni": anni,
                    "favorites": [{"code": c} for c in fav_codes]
                }
                c_label = qs.get("label", [""])[0].strip()
                if c_label:
                    cal_name = f"Orario UNIMIB - {c_label}"

        if not cfg or not cfg.get("anno") or not cfg.get("corso") or not cfg.get("anni"):
            return self.send_json(400, {"error": "Parametri insufficienti. Specificare 'code' oppure 'anno', 'corso' e 'anno2'."}, cache_control='no-store')

        extra_arg = qs.get("extra", [""])[0].strip()
        extra_courses = cfg.get("externalCourses") or []
        if extra_arg:
            try:
                parsed_extra = json.loads(extra_arg)
                if isinstance(parsed_extra, list):
                    extra_courses = parsed_extra
            except Exception:
                pass

        anno = cfg["anno"]
        corso = cfg["corso"]
        anni = tuple(sorted(cfg.get("anni", [])))
        favorites = cfg.get("favorites") or []
        fav_set = {f["code"].upper() for f in favorites if f.get("code")} if favorites else set()
        for ext in extra_courses:
            if ext.get("code"):
                fav_set.add(ext["code"].upper())
        if not fav_set and not favorites:
            fav_set = None

        filter_mode = qs.get("filter", ["target"])[0].strip().lower()
        if filter_mode == "all":
            fav_set = None

        try:
            weeks_count = max(1, min(12, int(qs.get("weeks", ["4"])[0])))
        except ValueError:
            weeks_count = 4

        # Start date: if omitted, default to current week Monday in Rome time
        start_date_str = qs.get("date", qs.get("start", [""]))[0].strip()
        start_monday = parse_date_to_monday(start_date_str) if start_date_str else get_monday()

        export_format = qs.get("format", ["ics"])[0].strip().lower()

        # 2. Fetch Weeks in Parallel
        weeks_mondays = [(start_monday + timedelta(days=7 * w)).strftime("%d-%m-%Y") for w in range(weeks_count)]

        ext_specs = []
        for ext in extra_courses:
            if not isinstance(ext, dict):
                continue
            ext_c = ext.get("corso", "").strip()
            if not ext_c:
                continue
            ext_a = ext.get("anno") or anno
            ext_y = ext.get("anno2") or []
            if isinstance(ext_y, str):
                ext_y = [ext_y]
            ext_y_tuple = tuple(sorted([y for y in ext_y if y]))
            if not ext_y_tuple:
                continue
            ext_code = (ext.get("code") or "").upper()
            ext_specs.append((ext_a, ext_c, ext_y_tuple, ext_code))

        week_cells = {mon: [] for mon in weeks_mondays}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(weeks_count * (1 + len(ext_specs)), 12)) as executor:
            future_to_info = {}
            for mon in weeks_mondays:
                f_main = executor.submit(_fetch_unimib_grid, anno, corso, anni, mon)
                future_to_info[f_main] = (mon, None)
                for (ea, ec, ey, ecode) in ext_specs:
                    f_ext = executor.submit(_fetch_unimib_grid, ea, ec, ey, mon)
                    future_to_info[f_ext] = (mon, ecode)

            for future in concurrent.futures.as_completed(future_to_info):
                mon, required_code = future_to_info[future]
                try:
                    cells = future.result()
                    if required_code:
                        cells = [c for c in cells if c.get("codice_insegnamento", "").upper() == required_code]
                    week_cells[mon].extend(cells)
                except Exception:
                    pass

        # 3. Deduplicate and Filter Events
        seen_events = set()
        events = []

        for mon in weeks_mondays:
            cells = week_cells.get(mon, [])
            for c in cells:
                course_code = c.get("codice_insegnamento", "")
                if fav_set and course_code.upper() not in fav_set:
                    continue

                day_date = c.get("data", "")
                start_time = c.get("ora_inizio", "")
                end_time = c.get("ora_fine", "")
                course_name = c.get("nome_insegnamento", "").strip()
                event_key = (day_date, start_time, end_time, course_name)

                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                events.append({
                    "id": c.get("id") or f"{day_date}_{start_time}_{course_code}",
                    "course": course_name,
                    "course_code": course_code,
                    "date": day_date,
                    "day_name": c.get("nome_giorno", "").capitalize(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "docente": c.get("docente", "").strip(),
                    "aula": c.get("aula", "").strip(),
                    "type": c.get("tipo", "Lezione"),
                    "is_canceled": c.get("Annullato") == "1"
                })

        def _sort_key(e):
            d = e.get("date", "")
            parts = d.split("-")
            if len(parts) == 3 and len(parts[2]) == 4:
                d = f"{parts[2]}-{parts[1]}-{parts[0]}"
            return (d, e.get("start_time", ""))

        events.sort(key=_sort_key)

        # Check if requester is an authenticated professor (confidentiality requirement)
        is_prof_auth = False
        auth_header = self.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else qs.get("token", [""])[0].strip()
        if token:
            sess = _redis_get(f"session:{token}")
            if sess and isinstance(sess, dict):
                clean_nick = sess.get("clean_nick", "")
                acc = _redis_get(f"account:{clean_nick}")
                if acc and isinstance(acc, dict) and acc.get("role") == "professor":
                    is_prof_auth = True

        # 4. Format Output
        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow([
                "Subject", "Start Date", "Start Time", "End Date", "End Time",
                "All Day Event", "Description", "Location"
            ])
            for ev in events:
                iso_date = _format_csv_date(ev["date"])
                desc = f"Docente: {ev['docente']}\nInsegnamento: {ev['course_code']}\nTipo: {ev['type']}"
                if is_prof_auth:
                    dt_info = _redis_get(f"lesson_teacher:{ev['id']}")
                    if dt_info and isinstance(dt_info, dict) and dt_info.get("designated_teacher"):
                        desc += f"\nDocente per questa lezione: {dt_info['designated_teacher']}"
                    c_note = _redis_get(f"course_note:{ev.get('course_code', '').upper()}") or _redis_get(f"lesson_note:{ev['id']}")
                    if c_note and isinstance(c_note, dict) and c_note.get("note"):
                        desc += f"\nNota Docente: {c_note['note']}"
                if ev["is_canceled"]:
                    desc += "\n[ANNULLATO]"
                writer.writerow([
                    _sanitize_csv_cell(ev["course"]),
                    _sanitize_csv_cell(iso_date),
                    _sanitize_csv_cell(ev["start_time"]),
                    _sanitize_csv_cell(iso_date),
                    _sanitize_csv_cell(ev["end_time"]),
                    "False",
                    _sanitize_csv_cell(desc),
                    _sanitize_csv_cell(ev["aula"] or "UNIMIB")
                ])

            data_bytes = output.getvalue().encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="orario_unimib.csv"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)

        elif export_format == "json":
            payload = {
                "calendar_name": cal_name,
                "course": corso,
                "academic_year": anno,
                "study_years": list(anni),
                "total_events": len(events),
                "events": events
            }
            data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="orario_unimib.json"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)

        else:
            # Default: iCalendar (.ics) [RFC 5545]
            now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            vcalendar_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//UNIMIB Orari//IT",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                _fold_ical_line(f"X-WR-CALNAME:{_escape_ical(cal_name)}"),
                "X-WR-TIMEZONE:Europe/Rome",
                "BEGIN:VTIMEZONE",
                "TZID:Europe/Rome",
                "X-LIC-LOCATION:Europe/Rome",
                "BEGIN:DAYLIGHT",
                "TZOFFSETFROM:+0100",
                "TZOFFSETTO:+0200",
                "TZNAME:CEST",
                "DTSTART:19700329T020000",
                "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
                "END:DAYLIGHT",
                "BEGIN:STANDARD",
                "TZOFFSETFROM:+0200",
                "TZOFFSETTO:+0100",
                "TZNAME:CET",
                "DTSTART:19701025T030000",
                "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
                "END:STANDARD",
                "END:VTIMEZONE"
            ]

            for ev in events:
                dt_start = _format_ical_date(ev["date"], ev["start_time"])
                dt_end = _format_ical_date(ev["date"], ev["end_time"])
                summary = ev["course"]
                if ev["is_canceled"]:
                    summary = f"[ANNULLATO] {summary}"
                location = ev["aula"] or "UNIMIB"
                description = f"Docente: {ev['docente']}\nInsegnamento: {ev['course_code']}\nTipo: {ev['type']}"
                if is_prof_auth:
                    dt_info = _redis_get(f"lesson_teacher:{ev['id']}")
                    if dt_info and isinstance(dt_info, dict) and dt_info.get("designated_teacher"):
                        description += f"\nDocente per questa lezione: {dt_info['designated_teacher']}"
                    c_note = _redis_get(f"course_note:{ev.get('course_code', '').upper()}") or _redis_get(f"lesson_note:{ev['id']}")
                    if c_note and isinstance(c_note, dict) and c_note.get("note"):
                        description += f"\nNota Docente: {c_note['note']}"

                vcalendar_lines.extend([
                    "BEGIN:VEVENT",
                    _fold_ical_line(f"UID:unimib-lesson-{ev['id']}@unimib.it"),
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART;TZID=Europe/Rome:{dt_start}",
                    f"DTEND;TZID=Europe/Rome:{dt_end}",
                    _fold_ical_line(f"SUMMARY:{_escape_ical(summary)}"),
                    _fold_ical_line(f"LOCATION:{_escape_ical(location)}"),
                    _fold_ical_line(f"DESCRIPTION:{_escape_ical(description)}"),
                    "STATUS:CANCELLED" if ev["is_canceled"] else "STATUS:CONFIRMED",
                    "END:VEVENT"
                ])

            vcalendar_lines.append("END:VCALENDAR")
            ics_text = "\r\n".join(vcalendar_lines) + "\r\n"
            data_bytes = ics_text.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="orario_unimib.ics"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)
