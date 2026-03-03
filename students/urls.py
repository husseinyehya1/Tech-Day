from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='list'),
    path('<int:pk>/', views.student_detail, name='detail'),
    path('<int:pk>/send-certificate/', views.send_certificate_email, name='send_certificate_email'),
    path('verify/<str:identifier>/', views.student_verify, name='verify'),
    path('certificate/<str:student_id>/', views.student_certificate, name='certificate'),
    path('تحديث-رقم-الهاتف/', views.update_phone_view, name='update_phone'),
    path('mark-badges-seen/', views.mark_badges_seen, name='mark_badges_seen'),
    path('submit-support-request/', views.student_submit_support_request, name='submit_support_request'),
]
