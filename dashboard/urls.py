from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('الطلاب/', views.admin_students_list, name='admin_students_list'),
    path('الطلاب/جديد/', views.admin_student_create, name='admin_student_create'),
    path('الطلاب/<int:pk>/تعديل/', views.admin_student_update, name='admin_student_update'),
    path('الطلاب/<int:pk>/إرسال-بيانات-الدخول/', views.admin_student_send_credentials, name='admin_student_send_credentials'),
    path('الطلاب/<int:pk>/حذف/', views.admin_student_delete, name='admin_student_delete'),
    path('الطلاب/<int:pk>/نقل/', views.admin_student_transfer, name='admin_student_transfer'),
    path('المجموعات/', views.admin_groups, name='admin_groups'),
    path('المجموعات/جديد/', views.admin_group_create, name='admin_group_create'),
    path('المجموعات/<int:pk>/تعديل/', views.admin_group_update, name='admin_group_update'),
    path('المشرفون/', views.admin_supervisors, name='admin_supervisors'),
    path('المشرفون/جديد/', views.admin_supervisor_create, name='admin_supervisor_create'),
    path('المشرفون/<int:pk>/تعديل/', views.admin_supervisor_update, name='admin_supervisor_update'),
    path('المجموعات/إعادة-توزيع/', views.admin_groups_redistribute, name='admin_groups_redistribute'),
    path('الورش/', views.admin_workshops, name='admin_workshops'),
    path('الورش/جديد/', views.admin_workshop_create, name='admin_workshop_create'),
    path('الورش/<int:pk>/تعديل/', views.admin_workshop_update, name='admin_workshop_update'),
    path('الورش/<int:pk>/تغيير-حالة/', views.admin_workshop_toggle_status, name='admin_workshop_toggle_status'),
    path('الجدول/', views.admin_schedule, name='admin_schedule'),
    path('الجدول/جلسة/<int:pk>/', views.admin_session_update, name='admin_session_update'),
    path('التنبيهات/', views.admin_notifications, name='admin_notifications'),
    path('التقارير/', views.admin_reports, name='admin_reports'),
    path('التقارير/export/csv/', views.admin_reports_export_csv, name='admin_reports_export_csv'),
    path('شاشة-العرض/', views.admin_public_screen, name='admin_public_screen'),
]
