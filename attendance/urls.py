from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('volunteer/', views.volunteer_dashboard, name='volunteer_dashboard'),
    path('volunteer/report-violation/', views.volunteer_report_violation, name='volunteer_report_violation'),
    path('volunteer/schedule/', views.volunteer_schedule, name='volunteer_schedule'),
    path('scan/', views.scan_qr, name='scan_qr'),
    path('scan/session/<int:session_id>/', views.scan_session_qr, name='scan_session_qr'),
    path('notes/', views.volunteer_notes, name='volunteer_notes'),
    path('award-points/', views.supervisor_award_points, name='award_points'),
    path('volunteer/search-students/', views.search_students, name='search_students'),
    path('scan/session/<int:session_id>/mark-all/', views.mark_all_group_present, name='mark_all_group_present'),
]
