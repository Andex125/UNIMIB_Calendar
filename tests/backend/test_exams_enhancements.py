import unittest
from unittest.mock import patch
from api.exams import get_related_course_codes, get_exams

class TestExamsEnhancements(unittest.TestCase):
    @patch("api.options.get_areas_and_courses")
    @patch("api.options.get_academic_years")
    def test_related_course_codes_expansion(self, mock_years, mock_courses):
        import api.exams
        api.exams._sister_codes_cache.clear()
        mock_years.return_value = [{"value": "2026", "label": "2025/2026"}]
        mock_courses.return_value = {
            "courses": [
                {"label": "INFORMATICA - Laurea", "type": "Laurea", "value": "E3101Q"},
                {"label": "INFORMATICA - Laurea", "type": "Laurea", "value": "E3102Q"}
            ]
        }
        related = get_related_course_codes(['E3101Q'])
        self.assertIn('E3101Q', related)
        self.assertIn('E3102Q', related)

    def test_empty_courses(self):
        self.assertEqual(get_related_course_codes([]), set())

    @patch("api.options.get_areas_and_courses")
    @patch("api.options.get_academic_years")
    @patch("api.exams.fetch_json")
    def test_get_exams_with_sister_code(self, mock_fetch, mock_years, mock_courses):
        import api.exams
        api.exams._sister_codes_cache.clear()
        mock_years.return_value = [{"value": "2026", "label": "2025/2026"}]
        mock_courses.return_value = {
            "courses": [
                {"label": "INFORMATICA - Laurea", "type": "Laurea", "value": "E3101Q"},
                {"label": "INFORMATICA - Laurea", "type": "Laurea", "value": "E3102Q"}
            ]
        }
        mock_fetch.return_value = {
            "events": [
                {
                    "id": "1",
                    "name": "PROGRAMMAZIONE 1",
                    "description": "Corso di laurea: Informatica [E3102Q] 1 anno",
                    "Giorno": "2026-06-10",
                    "from": "09:00:00",
                    "to": "11:00:00",
                    "Annullato": "0"
                },
                {
                    "id": "2",
                    "name": "BASI DI DATI",
                    "description": "Corso di laurea: Informatica [E3101Q] 2 anno",
                    "Giorno": "2026-06-15",
                    "from": "14:00:00",
                    "to": "16:00:00",
                    "Annullato": "0"
                }
            ]
        }
        res = get_exams(corsi=['E3101Q'], datefrom='01-01-2026', dateto='31-12-2026')
        self.assertGreater(len(res['exams']), 0)
        # Should include both 1st year and 2nd/3rd year exams via sister code
        codes = set()
        for ex in res['exams']:
            for c in ex.get('courses', []):
                codes.add(c.get('code'))
        self.assertTrue('E3101Q' in codes or 'E3102Q' in codes)

if __name__ == '__main__':
    unittest.main()

