"""本機試用／測試用路由：專案原本的路由 + 本功能的 /export/。"""
from django.urls import include, path

from config.urls import urlpatterns as project_urlpatterns

urlpatterns = list(project_urlpatterns) + [
    path('export/', include('timetable_export.urls')),
]
