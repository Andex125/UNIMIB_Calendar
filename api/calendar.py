import json
import re
import urllib.parse
from datetime import datetime, timedelta
import concurrent.futures

from api._common import (
    BaseApiHandler,
    get_monday,
    safe_ts,
    split_curricula,
    BoundedTTLCache,
    fetch_upstream,
    UpstreamError,
)

GRID_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/grid_call.php'
CACHE_TTL = 300
_grid_cache = BoundedTTLCache(maxsize=200, ttl_seconds=CACHE_TTL)
_safe_ts = safe_ts


class UnimibError(UpstreamError):
    """Base exception for UNIMIB upstream requests."""
    pass


class UnimibNetworkError(UnimibError):
    """Network connection error or timeout to UNIMIB."""
    pass


class UnimibParseError(UnimibError):
    """Invalid or non-JSON response from UNIMIB."""
    pass


def fetch_unimib_grid(anno, corso, anni_studio, date_str, force_refresh=False):
    cache_key = (anno, corso, tuple(sorted(anni_studio)), date_str)
    if not force_refresh:
        cached_data = _grid_cache.get(cache_key)
        if cached_data is not None:
            return cached_data

    params = [
        ('view', 'easycourse'),
        ('form-type', 'corso'),
        ('include', 'corso'),
        ('anno', anno),
        ('corso', corso),
        *[('anno2[]', a) for a in anni_studio],
        ('date', date_str),
        ('_lang', 'it'),
    ]
    url = f'{GRID_URL}?{urllib.parse.urlencode(params)}'

    try:
        content = fetch_upstream(url, timeout=12)
    except UpstreamError as e:
        raise UnimibNetworkError(f"Errore di rete o timeout durante la connessione a UNIMIB: {e}")
    except Exception as e:
        raise UnimibNetworkError(f"Errore di connessione a UNIMIB: {e}")

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise UnimibParseError(f"Risposta non JSON valida ricevuta da UNIMIB: {e}")

    if not isinstance(data, dict):
        raise UnimibParseError("Struttura dati non valida ricevuta da UNIMIB")

    _grid_cache.set(cache_key, data)
    return data


class handler(BaseApiHandler):
    def do_OPTIONS(self):
        self.handle_options(methods="GET, OPTIONS", headers="Content-Type")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        anno = qs.get('anno', [''])[0]
        corso = qs.get('corso', [''])[0]
        anni_studio = [a for a in qs.get('anno2', []) if a]
        date_arg = qs.get('date', [None])[0]
        extra_arg = qs.get('extra', [None])[0]
        is_refresh = qs.get('refresh', [''])[0] in ('1', 'true')

        if not re.fullmatch(r'\d{4}', anno) or not re.fullmatch(r'[A-Za-z0-9_-]+', corso) or not anni_studio:
            return self.send_json(400, {"error": "Specificare anno accademico, corso di studio e anno di studio"}, cache_control='no-store')

        if not date_arg:
            date_arg = get_monday().strftime('%d-%m-%Y')
        elif not re.fullmatch(r'\d{2}-\d{2}-\d{4}', date_arg):
            return self.send_json(400, {"error": "Parametro 'date' non valido (atteso gg-mm-aaaa)"}, cache_control='no-store')

        # Parse extra courses (from other degrees) if provided
        extra_courses = []
        if extra_arg:
            try:
                parsed_extra = json.loads(extra_arg)
                if isinstance(parsed_extra, list):
                    extra_courses = parsed_extra
            except Exception:
                pass

        try:
            # 1. Fetch main grid
            raw_data = fetch_unimib_grid(anno, corso, anni_studio, date_arg, force_refresh=is_refresh)
            if not isinstance(raw_data, dict):
                return self.send_json(502, {"error": "Risposta non valida dal server UNIMIB"}, cache_control='no-store')
            celle = sorted(raw_data.get("celle", []), key=safe_ts)
            giorni = raw_data.get("giorni", [])

            events = []
            seen_ids = set()

            for c in celle:
                course_name = c.get("nome_insegnamento", "").strip()
                day_date = c.get("data", "")
                start_time = c.get("ora_inizio", "")
                ev_id = c.get("id") or f"{day_date}_{start_time}_{course_name}"
                seen_ids.add(ev_id)

                events.append({
                    "id": ev_id,
                    "course": course_name,
                    "course_code": c.get("codice_insegnamento", ""),
                    "curricula": split_curricula(c.get("percorso_didattico", "")),
                    "type": c.get("tipo", ""),
                    "date": day_date,
                    "day_name": c.get("nome_giorno", "").capitalize(),
                    "start_time": start_time,
                    "end_time": c.get("ora_fine", ""),
                    "docente": c.get("docente", "").strip(),
                    "aula": c.get("aula", "").strip(),
                    "is_canceled": c.get("Annullato") == "1",
                    "is_external": False
                })

            # 2. Fetch external courses concurrently if present
            if extra_courses:
                ext_groups = {}
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
                    key = (ext_a, ext_c, ext_y_tuple)
                    if key not in ext_groups:
                        ext_groups[key] = []
                    ext_groups[key].append(ext)

                if ext_groups:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ext_groups), 4)) as executor:
                        future_to_group = {
                            executor.submit(fetch_unimib_grid, g_anno, g_corso, list(g_anni), date_arg, is_refresh): (g_anno, g_corso, g_anni, g_items)
                            for (g_anno, g_corso, g_anni), g_items in ext_groups.items()
                        }
                        for future in concurrent.futures.as_completed(future_to_group):
                            try:
                                g_anno, g_corso, g_anni, g_items = future_to_group[future]
                                ext_raw = future.result()
                                if not isinstance(ext_raw, dict):
                                    continue

                                # Merge any new days into giorni
                                existing_giorni_dates = {g.get("data") for g in giorni if isinstance(g, dict)}
                                for eg in ext_raw.get("giorni", []):
                                    if isinstance(eg, dict) and eg.get("data") and eg.get("data") not in existing_giorni_dates:
                                        giorni.append(eg)
                                        existing_giorni_dates.add(eg.get("data"))

                                codes_to_item = {item.get("code"): item for item in g_items if item.get("code")}

                                ext_cells = sorted(ext_raw.get("celle", []), key=safe_ts)
                                for c in ext_cells:
                                    c_code = c.get("codice_insegnamento", "")
                                    if codes_to_item and c_code not in codes_to_item:
                                        continue

                                    matched_item = codes_to_item.get(c_code, g_items[0] if g_items else {})
                                    course_name = c.get("nome_insegnamento", "").strip()
                                    day_date = c.get("data", "")
                                    start_time = c.get("ora_inizio", "")
                                    ev_id = c.get("id") or f"{day_date}_{start_time}_{course_name}"

                                    if ev_id in seen_ids:
                                        continue
                                    seen_ids.add(ev_id)

                                    events.append({
                                        "id": ev_id,
                                        "course": course_name,
                                        "course_code": c_code,
                                        "curricula": split_curricula(c.get("percorso_didattico", "")),
                                        "type": c.get("tipo", ""),
                                        "date": day_date,
                                        "day_name": c.get("nome_giorno", "").capitalize(),
                                        "start_time": start_time,
                                        "end_time": c.get("ora_fine", ""),
                                        "docente": c.get("docente", "").strip(),
                                        "aula": c.get("aula", "").strip(),
                                        "is_canceled": c.get("Annullato") == "1",
                                        "is_external": True,
                                        "external_corso": matched_item.get("corsoLabel") or matched_item.get("corso") or g_corso
                                    })
                            except Exception:
                                pass

            # Sort all events chronologically (date, start_time)
            def _sort_key(ev):
                d_val = ev.get("date", "")
                d_parts = d_val.split("-")
                if len(d_parts) == 3 and len(d_parts[2]) == 4:
                    d_val = f"{d_parts[2]}-{d_parts[1]}-{d_parts[0]}"
                return (d_val, ev.get("start_time", ""))

            events.sort(key=_sort_key)

            payload = {
                "monday_date": date_arg,
                "week_label": f"{raw_data.get('first_day_label', date_arg)} - {raw_data.get('last_day_label', '')}",
                "giorni": giorni,
                "total_events": len(events),
                "events": events
            }
            cache_ctrl = 'no-store' if is_refresh else 'public, s-maxage=300, stale-while-revalidate=600'
            self.send_json(200, payload, cache_control=cache_ctrl)
        except UpstreamError as e:
            self.send_json(502, {"error": str(e)}, cache_control='no-store')
        except Exception as e:
            self.send_json(502, {"error": f"Errore server: {e}"}, cache_control='no-store')
