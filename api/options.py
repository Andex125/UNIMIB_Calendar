import sys
import os
import json
import re
import urllib.parse

_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from api._common import (
    BaseApiHandler,
    BoundedTTLCache,
    fetch_upstream,
    UpstreamError,
)

COMBO_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/combo.php'
CACHE_TTL = 600
_cache = BoundedTTLCache(maxsize=100, ttl_seconds=CACHE_TTL)


def fetch_combo(params):
    url = f'{COMBO_URL}?{urllib.parse.urlencode(params)}'
    cached = _cache.get(url)
    if cached is not None:
        return cached
    try:
        text = fetch_upstream(url, timeout=12)
    except UpstreamError as e:
        raise UpstreamError(f"Impossibile recuperare opzioni UNIMIB: {e}")
    _cache.set(url, text)
    return text


def js_var(script, name):
    """Extracts the JSON literal assigned to `var <name> = ...;` in combo.php output."""
    m = re.search(r'var\s+' + re.escape(name) + r'\s*=\s*', script)
    if not m:
        return None
    try:
        return json.JSONDecoder().raw_decode(script, m.end())[0]
    except ValueError:
        return None


def get_academic_years():
    data = js_var(fetch_combo({'sw': 'ec_', 'aa': '1'}), 'anni_accademici_ec') or {}
    items = data.values() if isinstance(data, dict) else data
    years = [{"value": y["valore"], "label": y["label"]} for y in items if "valore" in y]
    years.sort(key=lambda y: y["value"], reverse=True)
    return years


def get_courses_data(anno):
    script = fetch_combo({'sw': 'ec_', 'aa': anno, 'page': 'corsi'})
    return js_var(script, 'elenco_corsi') or [], js_var(script, 'elenco_scuole') or []


def study_year_number(valore):
    return valore.rsplit('|', 1)[-1]


def get_areas_and_courses(anno):
    corsi, scuole = get_courses_data(anno)
    areas = [{"value": s["valore"], "label": s["label"]} for s in scuole]
    if any(not c.get("scuola") for c in corsi):
        areas.append({"value": "altri_corsi", "label": "Altri corsi"})

    courses = []
    for c in corsi:
        years = [
            {"value": a["valore"], "label": a["label"], "year": study_year_number(a["valore"])}
            for a in c.get("elenco_anni", [])
            if study_year_number(a["valore"]) != '0'
        ]
        courses.append({
            "value": c["valore"],
            "label": c["label"],
            "type": c.get("tipo", ""),
            "area": c.get("scuola") or "altri_corsi",
            "years": years
        })
    return {"areas": areas, "courses": courses}


def get_course_teachings(anno, corso):
    corsi, _ = get_courses_data(anno)
    course = next((c for c in corsi if c["valore"] == corso), None)
    if course is None:
        return None
    return {
        "label": course["label"],
        "type": course.get("tipo", ""),
        "area": course.get("scuola") or "altri_corsi",
        "years": [
            {
                "value": a["valore"],
                "label": a["label"],
                "year": study_year_number(a["valore"]),
                "teachings": [
                    {"code": i["valore"], "label": i["label"], "docente": i.get("docente", "")}
                    for i in a.get("elenco_insegnamenti", [])
                ]
            }
            for a in course.get("elenco_anni", [])
            if study_year_number(a["valore"]) != '0'
        ]
    }


class handler(BaseApiHandler):
    def do_OPTIONS(self):
        self.handle_options(methods="GET, OPTIONS", headers="Content-Type")

    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        anno = qs.get('anno', [''])[0]
        corso = qs.get('corso', [''])[0]

        try:
            if anno and not re.fullmatch(r'\d{4}', anno):
                return self.send_json(400, {"error": "Parametro 'anno' non valido"}, cache_control='no-store')
            if corso and not re.fullmatch(r'[A-Za-z0-9_-]+', corso):
                return self.send_json(400, {"error": "Parametro 'corso' non valido"}, cache_control='no-store')

            if not anno:
                payload = {"academic_years": get_academic_years()}
            elif not corso:
                payload = get_areas_and_courses(anno)
            else:
                payload = get_course_teachings(anno, corso)
                if payload is None:
                    return self.send_json(404, {"error": "Corso di studio non trovato"}, cache_control='no-store')

            self.send_json(200, payload, cache_control='public, s-maxage=3600, stale-while-revalidate=86400')
        except Exception as e:
            self.send_json(502, {"error": str(e)}, cache_control='no-store')
