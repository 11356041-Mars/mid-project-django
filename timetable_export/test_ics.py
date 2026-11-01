"""ics.py 的單元測試（不需要 Django、不需要資料庫）。

單獨執行：python -m unittest timetable_export.test_ics
"""
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from timetable_export import ics

FIXED_NOW = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)


def make_course(**kwargs):
    data = dict(
        id=1, code='IM101', name='資訊管理導論', teacher='黃燕萍',
        classroom='電708(承曦樓)', day_of_week=1, start_period=2, end_period=4,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def unfold(text):
    return text.replace('\r\n ', '')


class CourseSegmentsTests(unittest.TestCase):
    def test_simple_morning_course(self):
        self.assertEqual(ics.course_segments(2, 4), [((9, 10), (12, 0))])

    def test_single_period(self):
        self.assertEqual(ics.course_segments(1, 1), [((8, 10), (9, 0))])

    def test_course_crossing_lunch_is_split(self):
        self.assertEqual(
            ics.course_segments(4, 5),
            [((11, 10), (12, 0)), ((13, 30), (14, 20))],
        )

    def test_invalid_periods_are_ignored(self):
        self.assertEqual(ics.course_segments(10, 12), [])

    def test_format_segments(self):
        self.assertEqual(ics.format_segments([((9, 10), (12, 0))]), '09:10–12:00')


class FirstOccurrenceTests(unittest.TestCase):
    def test_same_weekday(self):
        # 2026-09-14 是星期一
        self.assertEqual(ics.first_occurrence(date(2026, 9, 14), 1), date(2026, 9, 14))

    def test_later_in_same_week(self):
        self.assertEqual(ics.first_occurrence(date(2026, 9, 14), 3), date(2026, 9, 16))

    def test_rolls_to_next_week(self):
        # 2026-09-16 是星期三，星期一的課要從下週一開始
        self.assertEqual(ics.first_occurrence(date(2026, 9, 16), 1), date(2026, 9, 21))


class TextHelpersTests(unittest.TestCase):
    def test_escape_text(self):
        self.assertEqual(ics.escape_text('a,b;c\\d\ne'), 'a\\,b\\;c\\\\d\\ne')

    def test_fold_line_respects_byte_limit_and_roundtrips(self):
        original = 'DESCRIPTION:' + '中文課程說明' * 30
        folded = ics.fold_line(original)
        for physical in folded.split('\r\n'):
            self.assertLessEqual(len(physical.encode('utf-8')), 75)
        self.assertEqual(unfold(folded), original)

    def test_short_line_not_folded(self):
        self.assertEqual(ics.fold_line('SUMMARY:abc'), 'SUMMARY:abc')


class BuildCalendarTests(unittest.TestCase):
    def build(self, courses=None, start=date(2026, 9, 14), weeks=18):
        courses = [make_course()] if courses is None else courses
        return ics.build_calendar(courses, start, weeks, calendar_name='測試生 的課表', now=FIXED_NOW)

    def test_basic_structure(self):
        text = self.build()
        self.assertTrue(text.startswith('BEGIN:VCALENDAR\r\n'))
        self.assertTrue(text.endswith('END:VCALENDAR\r\n'))
        self.assertNotIn('\n\n', text.replace('\r\n', '\n'))
        # 每個換行都必須是 CRLF
        self.assertEqual(text.count('\n'), text.count('\r\n'))

    def test_begin_end_are_balanced(self):
        text = unfold(self.build(courses=[make_course(), make_course(id=2, day_of_week=3)]))
        for name in ('VCALENDAR', 'VEVENT', 'VTIMEZONE', 'STANDARD'):
            self.assertEqual(text.count(f'BEGIN:{name}'), text.count(f'END:{name}'), name)
        self.assertEqual(text.count('BEGIN:VEVENT'), 2)

    def test_event_fields(self):
        text = unfold(self.build())
        self.assertIn('DTSTART;TZID=Asia/Taipei:20260914T091000', text)
        self.assertIn('DTEND;TZID=Asia/Taipei:20260914T120000', text)
        self.assertIn('RRULE:FREQ=WEEKLY;COUNT=18', text)
        self.assertIn('SUMMARY:資訊管理導論', text)
        self.assertIn('LOCATION:電708(承曦樓)', text)
        self.assertIn('DTSTAMP:20260901T000000Z', text)
        self.assertIn('UID:mis-course-1-1@timetable-export', text)

    def test_first_date_follows_weekday(self):
        text = unfold(self.build(courses=[make_course(day_of_week=3)]))
        self.assertIn('DTSTART;TZID=Asia/Taipei:20260916T091000', text)

    def test_course_crossing_lunch_makes_two_events(self):
        text = unfold(self.build(courses=[make_course(start_period=4, end_period=5)]))
        self.assertEqual(text.count('BEGIN:VEVENT'), 2)
        self.assertIn('T111000', text)
        self.assertIn('T133000', text)

    def test_special_characters_are_escaped(self):
        text = unfold(self.build(courses=[make_course(name='資料庫, 進階;實作')]))
        self.assertIn('SUMMARY:資料庫\\, 進階\\;實作', text)

    def test_course_with_invalid_day_or_period_is_skipped(self):
        text = self.build(courses=[make_course(day_of_week=7), make_course(id=2, start_period=10, end_period=11)])
        self.assertNotIn('BEGIN:VEVENT', text)

    def test_all_physical_lines_within_75_bytes(self):
        text = self.build(courses=[make_course(name='很長的課程名稱' * 10)])
        for physical in text.split('\r\n'):
            self.assertLessEqual(len(physical.encode('utf-8')), 75)

    def test_bad_weeks_rejected(self):
        with self.assertRaises(ValueError):
            self.build(weeks=0)
        with self.assertRaises(ValueError):
            self.build(weeks=ics.MAX_WEEKS + 1)


if __name__ == '__main__':
    unittest.main()
