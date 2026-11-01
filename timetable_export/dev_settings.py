"""本機試用／測試用設定：沿用專案原本的 config/settings.py，只把路由換成 dev_urls。

好處：不需要修改 config/urls.py 就能試用本功能。
    python manage.py runserver --settings=timetable_export.dev_settings
"""
from config.settings import *  # noqa: F401,F403

ROOT_URLCONF = 'timetable_export.dev_urls'
