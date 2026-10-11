import unittest
from unittest.mock import patch
import io
import json
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

api_rooms = load_module("api_rooms", "api/rooms.py")

class MockRoomsHandler(api_rooms.handler):
    def __init__(self, path):
        self.path = path
        self.response_status = None
        self.headers = {}
        self.output = io.BytesIO()
        self.wfile = self.output
        self.do_GET()

    def send_response(self, code):
        self.response_status = code

    def send_header(self, k, v):
        self.headers[k] = v

    def end_headers(self):
        pass

    def get_json(self):
        return json.loads(self.output.getvalue().decode("utf-8"))

class TestRoomsMidnightOccupancy(unittest.TestCase):
    def setUp(self):
        api_rooms._cache.clear()

    @patch.object(api_rooms, 'fetch_json')
    def test_midnight_realtime_free_status(self, mock_fetch):
        # Mock API returning events between 08:30 and 18:30
        mock_fetch.return_value = {
            "all_rooms": {
                "U6-01": {"room_code": "U6-01", "room_name": "Aula U6-01", "capacity": 150}
            },
            "events": [
                {
                    "CodiceAula": "U6-01",
                    "name": "Matematica Discreta",
                    "from": "08:30:00",
                    "to": "12:30:00",
                    "Annullato": "0"
                },
                {
                    "CodiceAula": "U6-01",
                    "name": "Fisica 1",
                    "from": "14:30:00",
                    "to": "18:30:00",
                    "Annullato": "0"
                }
            ]
        }

        # Query at 00:52 local client time in tempo reale
        res = api_rooms.get_room_occupancy(
            sede="U06",
            date_str="11-10-2026",
            time_str="now",
            client_time="00:52",
            client_date="11-10-2026"
        )

        self.assertEqual(res["total_rooms"], 1)
        self.assertEqual(res["free_rooms"], 1)
        self.assertEqual(res["occupied_rooms"], 0)
        self.assertEqual(res["check_time"], "00:52")
        self.assertTrue(res["is_today"])

        room = res["rooms"][0]
        self.assertTrue(room["is_free"], "At 00:52 room must be FREE, not occupied until 18:30!")
        self.assertEqual(room["free_until"], "08:30")
        self.assertIsNotNone(room["next_event"])
        self.assertEqual(room["next_event"]["from"], "08:30")

    @patch.object(api_rooms, 'fetch_json')
    def test_handler_query_params(self, mock_fetch):
        mock_fetch.return_value = {"all_rooms": {}, "events": []}

        # Valid time=now with client_time
        h1 = MockRoomsHandler("/api/rooms?sede=U06&date=11-10-2026&time=now&client_time=00:52")
        self.assertEqual(h1.response_status, 200)

        # Valid time=all
        h2 = MockRoomsHandler("/api/rooms?sede=U06&date=11-10-2026&time=all")
        self.assertEqual(h2.response_status, 200)

        # Valid time=14:30
        h3 = MockRoomsHandler("/api/rooms?sede=U06&date=11-10-2026&time=14:30")
        self.assertEqual(h3.response_status, 200)

        # Invalid time
        h4 = MockRoomsHandler("/api/rooms?sede=U06&date=11-10-2026&time=invalid")
        self.assertEqual(h4.response_status, 400)

if __name__ == '__main__':
    unittest.main()
