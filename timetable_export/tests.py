"""Django 端測試（view、權限、與 pages 模組的一致性）。

執行：python manage.py test timetable_export
（ics.py 本身的測試在 test_ics.py，會一起被執行）
"""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from pages.models import Course, Enrollment
from pages.views import PERIOD_INFO

from . import ics


class PeriodTimesConsistencyTests(SimpleTestCase):
    def test_period_times_match_pages_views(self):
        """ics.PERIOD_TIMES 必須與 pages/views.py 的 PERIOD_INFO 一致。"""
        for info in PERIOD_INFO:
            start, end = ics.PERIOD_TIMES[info['period']]
            expected = f'{start[0]:02d}:{start[1]:02d} - {end[0]:02d}:{end[1]:02d}'
            self.assertEqual(info['time'], expected, info['name'])


@override_settings(ROOT_URLCONF='timetable_export.dev_urls')
class ExportViewTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user('tx_student', password='pw', first_name='測試生')
        self.course = Course.objects.create(
            code='TX101', name='匯出測試課', teacher='王老師', classroom='藝406',
            day_of_week=2, start_period=2, end_period=4,
        )
        Enrollment.objects.create(user=self.student, course=self.course)
        self.index_url = reverse('timetable_export:index')
        self.download_url = reverse('timetable_export:download')

    def test_anonymous_is_redirected_to_login(self):
        for url in (self.index_url, self.download_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response['Location'].startswith(reverse('pages:login')))

    def test_page_lists_enrolled_courses(self):
        self.client.force_login(self.student)
        response = self.client.get(self.index_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '匯出測試課')
        self.assertContains(response, '09:10–12:00')

    def test_download_returns_ics_file(self):
        self.client.force_login(self.student)
        response = self.client.get(self.download_url, {'start': '2026-09-14', 'weeks': '10'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/calendar'))
        self.assertIn('attachment', response['Content-Disposition'])
        body = response.content.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('SUMMARY:匯出測試課', body)
        self.assertIn('RRULE:FREQ=WEEKLY;COUNT=10', body)
        self.assertIn('DTSTART;TZID=Asia/Taipei:20260915T091000', body)  # 星期二

    def test_download_does_not_change_enrollments(self):
        self.client.force_login(self.student)
        self.client.get(self.download_url, {'start': '2026-09-14', 'weeks': '10'})
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Course.objects.count(), 1)

    def test_bad_parameters_redirect_back_to_page(self):
        self.client.force_login(self.student)
        for params in ({'weeks': '99'}, {'weeks': 'abc'}, {'start': 'not-a-date'}):
            response = self.client.get(self.download_url, params)
            self.assertRedirects(response, self.index_url, fetch_redirect_response=False)

    def test_admin_has_no_personal_timetable(self):
        admin = User.objects.create_user('tx_admin', password='pw', is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(self.download_url)
        self.assertRedirects(response, self.index_url, fetch_redirect_response=False)

    def test_teacher_exports_only_taught_courses(self):
        teacher = User.objects.create_user('tx_teacher', password='pw', first_name='李老師')
        teacher.profile.role = 'TEACHER'
        teacher.profile.save()
        taught = Course.objects.create(
            code='TX202', name='教師授課測試', teacher='李老師', teacher_user=teacher,
            classroom='資401', day_of_week=4, start_period=5, end_period=6,
        )
        self.client.force_login(teacher)
        body = self.client.get(self.download_url).content.decode('utf-8')
        self.assertIn(f'SUMMARY:{taught.name}', body)
        self.assertNotIn('匯出測試課', body)
