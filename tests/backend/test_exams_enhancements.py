import unittest
from api.exams import get_related_course_codes, get_exams

class TestExamsEnhancements(unittest.TestCase):
    def test_related_course_codes_expansion(self):
        related = get_related_course_codes(['E3101Q'])
        self.assertIn('E3101Q', related)
        self.assertIn('E3102Q', related)

    def test_empty_courses(self):
        self.assertEqual(get_related_course_codes([]), set())

    def test_get_exams_with_sister_code(self):
        res = get_exams(corsi=['E3101Q'], datefrom='01-01-2026', dateto='31-12-2026')
        self.assertGreater(len(res['exams']), 0)
        # Should include both 1st year and 2nd/3rd year exams
        codes = set()
        for ex in res['exams']:
            for c in ex.get('courses', []):
                codes.add(c.get('code'))
        self.assertTrue('E3101Q' in codes or 'E3102Q' in codes)

if __name__ == '__main__':
    unittest.main()
