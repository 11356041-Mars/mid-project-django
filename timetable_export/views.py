"""課表匯出（.ics）— 頁面與下載。

只「讀取」pages.models 的資料，不會新增、修改或刪除任何課程與選課紀錄。
"""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from pages.models import Course, Enrollment

from .ics import (
    DEFAULT_WEEKS, MAX_WEEKS, build_calendar, course_segments, format_segments,
)

LOGIN_URL_NAME = 'pages:login'


def get_user_courses(user):
    """回傳 (課程清單, 身分)。

    學生 → 自己已選的課程；教師 → 自己授課的課程；教務管理員 → 沒有個人課表。
    身分判斷方式與 pages/views.py 的 index() 一致。
    """
    is_admin = user.is_staff or user.username == 'admin'
    if is_admin:
        return [], 'admin'

    role = getattr(getattr(user, 'profile', None), 'role', 'STUDENT')
    if role == 'TEACHER':
        courses = list(Course.objects.filter(teacher_user=user))
        role_name = 'teacher'
    else:
        courses = [e.course for e in Enrollment.objects.filter(user=user).select_related('course')]
        role_name = 'student'

    courses.sort(key=lambda c: (c.day_of_week, c.start_period))
    return courses, role_name


def _default_start():
    """預設開學日：本週一。"""
    today = timezone.localdate()
    return today - timedelta(days=today.weekday())


def _parse_params(request):
    """解析 ?start=YYYY-MM-DD&weeks=N，回傳 (開學日, 週數, 錯誤訊息)。"""
    raw_start = request.GET.get('start', '').strip()
    raw_weeks = request.GET.get('weeks', '').strip()

    try:
        start = date.fromisoformat(raw_start) if raw_start else _default_start()
    except ValueError:
        return None, None, '開學日期格式不正確，請重新選擇。'

    try:
        weeks = int(raw_weeks) if raw_weeks else DEFAULT_WEEKS
    except ValueError:
        return None, None, '週數必須是整數。'

    if not 1 <= weeks <= MAX_WEEKS:
        return None, None, f'週數請輸入 1～{MAX_WEEKS} 之間的數字。'

    return start, weeks, None


@login_required(login_url=LOGIN_URL_NAME)
@require_GET
def export_page(request):
    """匯出說明頁：預覽將匯出的課程，並設定開學日與週數。"""
    courses, role = get_user_courses(request.user)
    rows = [
        {
            'course': course,
            'time_range': format_segments(course_segments(course.start_period, course.end_period)),
        }
        for course in courses
    ]
    context = {
        'rows': rows,
        'role': role,
        'is_admin': role == 'admin',  # base.html 的導覽列會用到
        'default_start': _default_start().isoformat(),
        'default_weeks': DEFAULT_WEEKS,
        'max_weeks': MAX_WEEKS,
    }
    return render(request, 'timetable_export/export.html', context)


@login_required(login_url=LOGIN_URL_NAME)
@require_GET
def download_ics(request):
    """下載 .ics 檔。"""
    start, weeks, error = _parse_params(request)
    if error:
        messages.error(request, error)
        return redirect('timetable_export:index')

    courses, _role = get_user_courses(request.user)
    if not courses:
        messages.warning(request, '目前沒有可匯出的課程。')
        return redirect('timetable_export:index')

    display_name = request.user.first_name or request.user.username
    content = build_calendar(courses, start, weeks, calendar_name=f'{display_name} 的課表')

    response = HttpResponse(content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="timetable.ics"'
    return response
