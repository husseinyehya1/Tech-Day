from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='list'),
    path('<int:pk>/', views.student_detail, name='detail'),
    path('<int:pk>/send-certificate/', views.send_certificate_email, name='send_certificate_email'),
    path('verify/<str:identifier>/', views.student_verify, name='verify'),
    path('certificate/<str:student_id>/', views.student_certificate, name='certificate'),
]
