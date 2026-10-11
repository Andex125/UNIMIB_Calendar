import json
import re
import urllib.parse
from datetime import datetime, timedelta
import concurrent.futures

from api._common import (
    BaseApiHandler,
    BoundedTTLCache,
    get_rome_now,
    DAYS_IT,
    MONTHS_IT,
    fetch_upstream,
    UpstreamError,
)

ROOMS_CALL_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/rooms_call.php'
COMBO_URL = 'https://gestioneorari.didattica.unimib.it/PortaleStudentiUnimib/combo.php'
CACHE_TTL = 300  # 5 minutes

_cache = BoundedTTLCache(maxsize=150, ttl_seconds=CACHE_TTL)
get_italy_now = get_rome_now


def fetch_json(url, timeout=12):
    cached = _cache.get(url)
    if cached is not None:
        return cached
    text = fetch_upstream(url, timeout=timeout)
    data = json.loads(text)
    _cache.set(url, data)
    return data


def get_buildings():
    url = f"{COMBO_URL}?sw=rooms_"
    cached = _cache.get(url)
    if cached is not None:
        return cached
    text = fetch_upstream(url, timeout=12)
    m = re.search(r'var\s+elenco_sedi\s*=\s*', text)
    if not m:
        return []
    sedi = json.JSONDecoder().raw_decode(text, m.end())[0]
    result = []
    for s in sedi:
        val = s.get("valore")
        label = s.get("label")
        if val and label and val != "SPAZI_MANCANTI":
            result.append({"value": val, "label": label})

    # Sort with common Bicocca buildings (U1, U2, ...) nicely
    def sort_key(item):
        v = item["value"]
        m_bld = re.match(r'^U0*(\d+)', v)
        if m_bld:
            return (0, int(m_bld.group(1)), item["label"])
        return (1, 0, item["label"])

    result.sort(key=sort_key)
    _cache.set(url, result)
    return result


def parse_time_str(t_str):
    if not t_str:
        return 0
    parts = t_str.split(':')
    h = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return h * 60 + m


def format_minutes(mins):
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def get_room_occupancy(sede, date_str, time_str=None, client_time=None, client_date=None):
    now_it = get_rome_now()
    today_str = now_it.strftime('%d-%m-%Y')
    is_today = (date_str == today_str) or (bool(client_date) and date_str == client_date) or (time_str == 'now')

    # Parse date to Italian format representations
    date_clean = date_str.replace('/', '-')
    dt_obj = None
    for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
        try:
            dt_obj = datetime.strptime(date_clean, fmt)
            break
        except ValueError:
            pass

    if dt_obj:
        day_name = DAYS_IT.get(dt_obj.weekday(), '')
        month_name = MONTHS_IT.get(dt_obj.month, '')
        date_formatted = dt_obj.strftime('%d/%m/%Y')
        date_long = f"{day_name} {dt_obj.day} {month_name} {dt_obj.year}"
    else:
        day_name = ''
        date_formatted = date_str.replace('-', '/')
        date_long = date_str

    if time_str == 'all':
        check_mins = None
    elif time_str and time_str != 'now':
        check_mins = parse_time_str(time_str)
    elif time_str == 'now' or is_today:
        if client_time:
            check_mins = parse_time_str(client_time)
        else:
            check_mins = now_it.hour * 60 + now_it.minute
    else:
        check_mins = None

    params = [
        ('form-type', 'rooms'),
        ('sede[]', sede),
        ('date', date_str),
        ('_lang', 'it')
    ]
    query_url = f"{ROOMS_CALL_URL}?{urllib.parse.urlencode(params)}"
    raw = fetch_json(query_url)

    all_rooms_dict = raw.get("all_rooms", {})
    if isinstance(all_rooms_dict, list):
        all_rooms_dict = {str(r.get("room_code", r.get("id"))): r for r in all_rooms_dict}

    raw_events = raw.get("events", [])

    # Group events by room code
    room_events_map = {}
    for ev in raw_events:
        if ev.get("Annullato") == "1":
            continue
        code = ev.get("CodiceAula") or ev.get("NomeAula")
        if not code:
            continue

        docenti = []
        for u in ev.get("Utenti", []):
            cognome = u.get("Cognome", "").strip()
            nome = u.get("Nome", "").strip()
            full = f"{cognome} {nome}".strip()
            if full:
                docenti.append(full)
        if not docenti and ev.get("utenti"):
            docenti = [ev.get("utenti").strip()]
        if not docenti and ev.get("Prenotante"):
            docenti = [ev.get("Prenotante").strip()]

        from_raw = ev.get("from", "")[:5]
        to_raw = ev.get("to", "")[:5]
        from_mins = parse_time_str(from_raw)
        to_mins = parse_time_str(to_raw)

        event_item = {
            "id": ev.get("id"),
            "name": ev.get("name", "").strip(),
            "type": ev.get("type") or ev.get("tipo") or "Evento",
            "from": from_raw,
            "to": to_raw,
            "from_mins": from_mins,
            "to_mins": to_mins,
            "docenti": docenti,
            "description": ev.get("description", "").strip(),
            "notes": ev.get("PublicNotes", "").strip() or ev.get("Note", "").strip()
        }
        room_events_map.setdefault(code, []).append(event_item)

    # Sort events by start time for each room
    for code in room_events_map:
        room_events_map[code].sort(key=lambda x: x["from_mins"])

    # Prepare room list
    rooms_output = []
    if not all_rooms_dict:
        rooms_meta = raw.get("rooms", {})
        for r_code, r_val in rooms_meta.items():
            all_rooms_dict[r_code] = {
                "room_code": r_code,
                "room_name": r_val.get("nome", r_code),
                "capacity": r_val.get("capacity", 0)
            }

    # Building hours (U12 open until 23:00, other buildings close around 20:00)
    closing_mins = 1380 if 'U12' in sede.upper() else 1200
    opening_mins = 450  # 07:30
    is_building_closed = bool(check_mins is not None and (check_mins >= closing_mins or check_mins < opening_mins))

    for code, meta in all_rooms_dict.items():
        evs = room_events_map.get(code, [])
        r_name = meta.get("room_name") or meta.get("NomeAula") or code
        capacity = meta.get("capacity") or 0
        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            capacity = 0

        is_free = True
        current_event = None
        next_event = None
        chained_next_event = None
        occupied_from = None
        occupied_until = None
        free_until = None

        if check_mins is not None:
            for i, ev in enumerate(evs):
                if ev["from_mins"] <= check_mins < ev["to_mins"]:
                    is_free = False
                    current_event = ev
                    occupied_from = ev["from"]
                    curr_end_mins = ev["to_mins"]
                    curr_end = ev["to"]
                    for j in range(i + 1, len(evs)):
                        sub = evs[j]
                        if sub["from_mins"] <= curr_end_mins + 15 and sub["to_mins"] > curr_end_mins:
                            curr_end_mins = sub["to_mins"]
                            curr_end = sub["to"]
                            if chained_next_event is None:
                                chained_next_event = sub
                    occupied_until = curr_end
                    break
                elif ev["from_mins"] > check_mins and next_event is None:
                    next_event = ev

            if is_free:
                if next_event:
                    free_until = next_event["from"]
                elif is_building_closed:
                    free_until = "Edificio chiuso"
                else:
                    free_until = "fine giornata"
        else:
            is_free = (len(evs) == 0)
            if evs:
                occupied_from = evs[0]["from"]
                occupied_until = evs[-1]["to"]
                current_event = evs[0]
                if len(evs) > 1:
                    chained_next_event = evs[1]
            else:
                free_until = "fine giornata"

        rooms_output.append({
            "code": code,
            "name": r_name,
            "capacity": capacity,
            "is_free": is_free,
            "current_event": current_event,
            "next_event": next_event,
            "chained_next_event": chained_next_event,
            "occupied_from": occupied_from,
            "occupied_until": occupied_until,
            "free_until": free_until,
            "events_count": len(evs),
            "events": evs
        })

    # Sort rooms: free rooms first, then by name
    rooms_output.sort(key=lambda r: (not r["is_free"], r["name"]))

    return {
        "sede": sede,
        "date": date_str,
        "date_formatted": date_formatted,
        "date_long": date_long,
        "day_name": day_name,
        "is_today": is_today,
        "is_building_closed": is_building_closed,
        "check_time": format_minutes(check_mins) if check_mins is not None else None,
        "total_rooms": len(rooms_output),
        "free_rooms": sum(1 for r in rooms_output if r["is_free"]),
        "occupied_rooms": sum(1 for r in rooms_output if not r["is_free"]),
        "rooms": rooms_output
    }


def get_campus_summary(date_str, time_str=None, client_time=None, client_date=None):
    """Aggregate room availability across key campus buildings."""
    buildings = get_buildings()
    summary_list = []

    def _fetch_bld(bld):
        try:
            val = bld["value"]
            res = get_room_occupancy(val, date_str, time_str, client_time, client_date)
            return {
                "value": val,
                "label": bld["label"],
                "total_rooms": res["total_rooms"],
                "free_rooms": res["free_rooms"],
                "occupied_rooms": res["occupied_rooms"],
                "is_building_closed": res.get("is_building_closed", False)
            }
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_fetch_bld, b) for b in buildings]
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                summary_list.append(res)

    def _bld_sort_key(b):
        m = re.match(r'^U0*(\d+)', b["value"])
        return (0, int(m.group(1))) if m else (1, b["value"])

    summary_list.sort(key=_bld_sort_key)
    return {
        "summary": True,
        "date": date_str,
        "check_time": client_time or time_str or "now",
        "total_buildings": len(summary_list),
        "total_free_rooms": sum(b["free_rooms"] for b in summary_list),
        "total_rooms": sum(b["total_rooms"] for b in summary_list),
        "buildings": summary_list
    }


class handler(BaseApiHandler):
    def do_OPTIONS(self):
        self.handle_options(methods="GET, OPTIONS", headers="Content-Type")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        sede = qs.get('sede', [''])[0]
        date_arg = qs.get('date', [''])[0]
        time_arg = qs.get('time', [''])[0]
        client_time_arg = qs.get('client_time', [''])[0]
        client_date_arg = qs.get('client_date', [''])[0]
        mode = qs.get('mode', [''])[0]

        try:
            if not sede and mode != 'summary':
                buildings = get_buildings()
                return self.send_json(200, {"buildings": buildings}, cache_control='public, s-maxage=3600, stale-while-revalidate=86400')

            if sede and sede != 'all' and not re.fullmatch(r'[A-Za-z0-9_.\-]+', sede):
                return self.send_json(400, {"error": "Parametro 'sede' non valido"}, cache_control='no-store')

            if not date_arg:
                now_it = get_rome_now()
                date_arg = now_it.strftime('%d-%m-%Y')
            elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_arg):
                y, m, d = date_arg.split('-')
                date_arg = f"{d}-{m}-{y}"
            elif not re.fullmatch(r'\d{2}-\d{2}-\d{4}', date_arg):
                return self.send_json(400, {"error": "Parametro 'date' non valido (atteso GG-MM-AAAA)"}, cache_control='no-store')

            if time_arg and time_arg not in ('now', 'all') and not re.fullmatch(r'\d{1,2}:\d{2}', time_arg):
                return self.send_json(400, {"error": "Parametro 'time' non valido (atteso HH:MM, 'now' o 'all')"}, cache_control='no-store')

            if client_time_arg and not re.fullmatch(r'\d{1,2}:\d{2}', client_time_arg):
                return self.send_json(400, {"error": "Parametro 'client_time' non valido (atteso HH:MM)"}, cache_control='no-store')

            if client_date_arg and not re.fullmatch(r'\d{2}-\d{2}-\d{4}', client_date_arg):
                return self.send_json(400, {"error": "Parametro 'client_date' non valido (atteso GG-MM-AAAA)"}, cache_control='no-store')

            if sede == 'all' or mode == 'summary':
                payload = get_campus_summary(date_arg, time_arg, client_time_arg, client_date_arg)
            else:
                payload = get_room_occupancy(sede, date_arg, time_arg, client_time_arg, client_date_arg)

            self.send_json(200, payload, cache_control='no-cache')
        except Exception as e:
            self.send_json(502, {"error": str(e)}, cache_control='no-store')
