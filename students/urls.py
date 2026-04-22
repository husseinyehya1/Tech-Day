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
    path('workshop-note/submit/', views.submit_workshop_note, name='submit_workshop_note'),
    path('submit-support-request/', views.student_submit_support_request, name='submit_support_request'),
    path('حجز-مكان-في-الفعالية/', views.register_current_event, name='register_current_event'),
    path('تأكيد-حجز-الفعالية/', views.event_confirmation, name='event_confirmation'),
    path('confirm-registration/', views.confirm_registration, name='confirm_registration'),
]
