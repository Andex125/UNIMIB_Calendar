import sys
import os
import json
import re
import urllib.parse
from datetime import datetime, timedelta
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
    get_redis_creds,
)

GRID_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/grid_call.php'

SHARED_COLORS = [
    "#3B82F6",  # Royal Blue
    "#F97316",  # Warm Orange
    "#8B5CF6",  # Vivid Purple
    "#10B981",  # Emerald Green
    "#EC4899",  # Hot Pink
    "#EAB308",  # Amber Gold
    "#6366F1",  # Indigo
    "#F43F5E",  # Rose Coral
    "#84CC16",  # Lime Green
    "#06B6D4",  # Electric Cyan
    "#A855F7",  # Orchid Purple
    "#D97706",  # Bronze Gold
]

MAX_PROFILES = 8  # safety cap
CACHE_TTL = 300   # 5 minutes in-memory cache for UNIMIB grids

_grid_cache = BoundedTTLCache(maxsize=200, ttl_seconds=CACHE_TTL)
_safe_ts = safe_ts
_redis_get = redis_get


def _get_monday(date_str: str) -> str:
    """Given DD-MM-YYYY or YYYY-MM-DD, return the Monday of that week in DD-MM-YYYY."""
    if not date_str:
        return get_monday().strftime("%d-%m-%Y")
    try:
        return parse_date_to_monday(date_str).strftime("%d-%m-%Y")
    except Exception:
        return get_monday().strftime("%d-%m-%Y")


def _resolve_profile(code: str):
    """Try resolving profile by public share code, account or legacy profile."""
    try:
        prof = _redis_get(f"share:{code}")
        if prof and isinstance(prof, dict):
            return code, prof
        prof = _redis_get(f"account:{code}")
        if prof and isinstance(prof, dict):
            return code, prof
        prof = _redis_get(f"profile:{code}")
        if prof and isinstance(prof, dict):
            return code, prof
    except Exception:
        pass
    return code, None


def _fetch_raw_grid(anno: str, corso: str, anni_tuple: tuple, monday_str: str) -> list:
    """Fetch raw UNIMIB cells with memory caching."""
    if not anno or not corso or not anni_tuple:
        return []

    cache_key = (anno, corso, anni_tuple, monday_str)
    cached = _grid_cache.get(cache_key)
    if cached is not None:
        return cached

    params = [
        ("view",      "easycourse"),
        ("form-type", "corso"),
        ("include",   "corso"),
        ("anno",      anno),
        ("corso",     corso),
        *[("anno2[]", a) for a in anni_tuple],
        ("date",      monday_str),
        ("_lang",     "it"),
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


def _extract_events_from_cells(cells: list, favorite_codes: list | None) -> list:
    """Filter pre-fetched cells according to student favorites."""
    fav_set = {c.upper() for c in favorite_codes} if favorite_codes else None
    events = []
    for c in cells:
        course_code = c.get("codice_insegnamento", "")
        if fav_set and course_code.upper() not in fav_set:
            continue
        events.append({
            "date":        c.get("data", ""),
            "day_name":    c.get("nome_giorno", "").capitalize(),
            "start_time":  c.get("ora_inizio", ""),
            "end_time":    c.get("ora_fine", ""),
            "course":      c.get("nome_insegnamento", "").strip(),
            "course_code": course_code,
            "aula":        c.get("aula", "").strip(),
            "docente":     c.get("docente", "").strip(),
            "is_canceled": c.get("Annullato") == "1",
        })
    return events


class handler(BaseApiHandler):

    def _qs(self) -> dict:
        parsed = urllib.parse.urlparse(self.path)
        return dict(urllib.parse.parse_qsl(parsed.query))

    def do_OPTIONS(self):
        self.handle_options(methods="GET, OPTIONS", headers="Content-Type")

    def do_GET(self):
        qs = self._qs()
        raw_codes = [i.strip().lower() for i in (qs.get("codes", "") or qs.get("ids", "")).split(",") if i.strip()]
        codes = [c for c in raw_codes if re.match(r'^[a-z0-9_-]{3,30}$', c)][:MAX_PROFILES]
        date = qs.get("date", "").strip()

        if not codes:
            return self.send_json(400, {"error": "codes parameter required and must be alphanumeric"}, cache_control='no-store')

        monday = _get_monday(date)

        # 1. Parallel Profile Resolution via ThreadPoolExecutor
        resolved_profiles = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(codes), 8)) as executor:
            future_to_code = {executor.submit(_resolve_profile, c): c for c in codes}
            for future in concurrent.futures.as_completed(future_to_code):
                try:
                    c, prof = future.result()
                    if prof:
                        resolved_profiles[c] = prof
                except Exception:
                    pass

        # 2. Collect Distinct UNIMIB Grids to Fetch
        needed_grids = set()
        students_plan = []

        for idx, code in enumerate(codes):
            profile = resolved_profiles.get(code)
            if not profile:
                continue

            color = SHARED_COLORS[idx % len(SHARED_COLORS)]
            share_id = profile.get("share_code", code.upper())
            nickname = profile.get("nickname", share_id)
            cfg = profile.get("config") or {}

            anno = cfg.get("anno", "")
            corso = cfg.get("corso", "")
            anni = tuple(sorted(cfg.get("anni", [])))

            favorites = cfg.get("favorites") or []
            favorite_codes = [f.get("code", "") for f in favorites if f.get("code")] if favorites else None

            grid_keys = []
            if anno and corso and anni:
                grid_key = (anno, corso, anni)
                needed_grids.add(grid_key)
                grid_keys.append((grid_key, favorite_codes))

            external_courses = cfg.get("externalCourses") or []
            for ext in external_courses:
                if not isinstance(ext, dict):
                    continue
                ext_c = ext.get("corso", "").strip()
                if not ext_c:
                    continue
                ext_a = ext.get("anno") or anno
                ext_y = ext.get("anno2") or []
                if isinstance(ext_y, str):
                    ext_y = [ext_y]
                ext_tuple = tuple(sorted([y for y in ext_y if y]))
                if not ext_tuple:
                    continue
                ext_grid_key = (ext_a, ext_c, ext_tuple)
                needed_grids.add(ext_grid_key)
                ext_code = ext.get("code")
                grid_keys.append((ext_grid_key, [ext_code] if ext_code else None))

            students_plan.append({
                "share_id":       share_id,
                "nickname":       nickname,
                "color":          color,
                "grid_keys":      grid_keys,
            })

        # 3. Parallel Fetch of Distinct UNIMIB Grids
        grids_data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(len(needed_grids), 1), 8)) as executor:
            future_to_grid = {
                executor.submit(_fetch_raw_grid, g[0], g[1], g[2], monday): g
                for g in needed_grids
            }
            for future in concurrent.futures.as_completed(future_to_grid):
                grid_key = future_to_grid[future]
                try:
                    grids_data[grid_key] = future.result()
                except Exception:
                    grids_data[grid_key] = []

        # 4. Extract and Filter Events for Each Student
        profiles_out = []
        all_events = []

        for sp in students_plan:
            profiles_out.append({
                "id":         sp["share_id"],
                "share_code": sp["share_id"],
                "nickname":   sp["nickname"],
                "color":      sp["color"]
            })

            for (g_key, allowed_codes) in sp.get("grid_keys", []):
                if g_key and g_key in grids_data:
                    cells = grids_data[g_key]
                    student_events = _extract_events_from_cells(cells, allowed_codes)
                    for ev in student_events:
                        ev["profile_id"] = sp["share_id"]
                        ev["nickname"]   = sp["nickname"]
                        ev["color"]      = sp["color"]
                    all_events.extend(student_events)

        def _sort_key(e):
            d = e.get("date", "")
            parts = d.split("-")
            if len(parts) == 3 and len(parts[2]) == 4:
                d = f"{parts[2]}-{parts[1]}-{parts[0]}"
            return (d, e.get("start_time", ""), e.get("nickname", ""))

        all_events.sort(key=_sort_key)

        return self.send_json(200, {
            "profiles": profiles_out,
            "events":   all_events,
            "week":     monday
        }, cache_control='public, s-maxage=300, stale-while-revalidate=600')
