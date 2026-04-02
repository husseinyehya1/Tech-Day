from django.urls import path
from . import views

app_name = 'public_screen'

urlpatterns = [
    path('', views.public_screen_view, name='public_screen'),
    path('mobile-app/', views.mobile_app_download_view, name='mobile_app_download'),
    path('تنزيل-تطبيق-الهاتف/', views.mobile_app_download_view, name='mobile_app_download_ar'),
    path('success/', views.registration_success_view, name='registration_success'),
    path('terms/', views.terms_view, name='terms'),
    path('f/<str:token>/', views.public_form_view, name='public_form'),
    path('f/<str:token>/success/', views.public_form_success_view, name='public_form_success'),
    path('f/<str:token>/failed/', views.public_form_failed_view, name='public_form_failed'),
]
