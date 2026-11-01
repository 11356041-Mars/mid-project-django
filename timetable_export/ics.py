"""課表匯出 .ics 的核心邏輯。

這支檔案是「純 Python」，完全不依賴 Django，因此可以單獨測試：
    python -m unittest timetable_export.test_ics
"""
from datetime import datetime, timedelta, timezone

TZID = 'Asia/Taipei'
DEFAULT_WEEKS = 18   # 預設重複週數（一學期約 18 週）
MAX_WEEKS = 30       # 週數上限，避免有人輸入離譜的數字

# 各節次的 (開始時間, 結束時間)。
# 需與 pages/views.py 的 PERIOD_INFO 一致（tests.py 會自動檢查，不一致會測試失敗）。
PERIOD_TIMES = {
    1: ((8, 10), (9, 0)),
    2: ((9, 10), (10, 0)),
    3: ((10, 10), (11, 0)),
    4: ((11, 10), (12, 0)),
    5: ((13, 30), (14, 20)),
    6: ((14, 25), (15, 15)),
    7: ((15, 25), (16, 15)),
    8: ((16, 20), (17, 10)),
    9: ((17, 15), (18, 5)),
}
LUNCH_AFTER_PERIOD = 4  # 第四節之後是午休 12:00~13:30，跨午休的課要拆成上、下午兩段

# 台灣沒有日光節約時間，固定 +0800；附上 VTIMEZONE 讓 Outlook 等軟體也能正確辨識
VTIMEZONE = [
    'BEGIN:VTIMEZONE',
    f'TZID:{TZID}',
    'BEGIN:STANDARD',
    'DTSTART:19700101T000000',
    'TZOFFSETFROM:+0800',
    'TZOFFSETTO:+0800',
    'TZNAME:CST',
    'END:STANDARD',
    'END:VTIMEZONE',
]


def course_segments(start_period, end_period):
    """回傳一門課實際的上課時段 [((時, 分), (時, 分)), ...]。

    跨午休（例如第 4~5 節）會拆成上午、下午兩段；不存在的節次會被忽略。
    """
    periods = [p for p in range(start_period, end_period + 1) if p in PERIOD_TIMES]
    morning = [p for p in periods if p <= LUNCH_AFTER_PERIOD]
    afternoon = [p for p in periods if p > LUNCH_AFTER_PERIOD]
    segments = []
    for group in (morning, afternoon):
        if group:
            segments.append((PERIOD_TIMES[group[0]][0], PERIOD_TIMES[group[-1]][1]))
    return segments


def format_segments(segments):
    """把時段轉成給人看的字串，例如 '09:10–12:00'。"""
    return '、'.join(
        f'{s[0]:02d}:{s[1]:02d}–{e[0]:02d}:{e[1]:02d}' for s, e in segments
    )


def first_occurrence(start_date, day_of_week):
    """從 start_date 起（含當天）第一個「星期 day_of_week」的日期（1=週一 … 5=週五）。"""
    offset = ((day_of_week - 1) - start_date.weekday()) % 7
    return start_date + timedelta(days=offset)


def escape_text(value):
    """依 RFC 5545 跳脫文字欄位中的特殊字元。"""
    return (
        str(value)
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\r\n', '\n')
        .replace('\n', '\\n')
    )


def fold_line(line, limit=75):
    """依 RFC 5545 把超過 75 bytes 的行折行（以 UTF-8 位元組計算，不會切壞中文字）。"""
    pieces = []
    current = ''
    current_bytes = 0
    for ch in line:
        size = len(ch.encode('utf-8'))
        if current_bytes + size > limit:
            pieces.append(current)
            current = ' ' + ch          # 續行開頭的空白也算在 75 bytes 內
            current_bytes = 1 + size
        else:
            current += ch
            current_bytes += size
    pieces.append(current)
    return '\r\n'.join(pieces)


def build_calendar(courses, start_date, weeks, calendar_name='我的課表', now=None):
    """產生 .ics 文字。

    courses     : 具有 id、name、code、teacher、classroom、day_of_week、
                  start_period、end_period 屬性的物件（例如 pages.models.Course）
    start_date  : datetime.date，開學日；每門課從這天起的第一個該星期開始
    weeks       : 每週重複幾次（1 ~ MAX_WEEKS）
    now         : 測試用，需為帶時區的 datetime；預設為現在（UTC）
    """
    if not 1 <= weeks <= MAX_WEEKS:
        raise ValueError(f'weeks 必須介於 1 到 {MAX_WEEKS}')

    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//MIS Course Selection//Timetable Export//ZH',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{escape_text(calendar_name)}',
        f'X-WR-TIMEZONE:{TZID}',
    ]
    lines.extend(VTIMEZONE)

    for course in courses:
        if course.day_of_week not in (1, 2, 3, 4, 5):
            continue
        day = first_occurrence(start_date, course.day_of_week)
        segments = course_segments(course.start_period, course.end_period)
        for index, (start, end) in enumerate(segments, start=1):
            date_text = day.strftime('%Y%m%d')
            description = f'課程代碼：{course.code}\n授課教師：{course.teacher}'
            lines.extend([
                'BEGIN:VEVENT',
                # UID 固定（不含日期），重新匯出再匯入時，行事曆才會視為同一個活動
                f'UID:mis-course-{course.id}-{index}@timetable-export',
                f'DTSTAMP:{stamp}',
                f'DTSTART;TZID={TZID}:{date_text}T{start[0]:02d}{start[1]:02d}00',
                f'DTEND;TZID={TZID}:{date_text}T{end[0]:02d}{end[1]:02d}00',
                f'RRULE:FREQ=WEEKLY;COUNT={weeks}',
                f'SUMMARY:{escape_text(course.name)}',
                f'LOCATION:{escape_text(course.classroom)}',
                f'DESCRIPTION:{escape_text(description)}',
                'END:VEVENT',
            ])

    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold_line(line) for line in lines) + '\r\n'
