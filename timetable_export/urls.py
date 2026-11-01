from django.urls import path

from . import views

app_name = 'timetable_export'

urlpatterns = [
    path('', views.export_page, name='index'),
    path('download/', views.download_ics, name='download'),
]
