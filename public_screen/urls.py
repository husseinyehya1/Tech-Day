from django.urls import path
from . import views

app_name = 'public_screen'

urlpatterns = [
    path('', views.public_screen_view, name='public_screen'),
    path('success/', views.registration_success_view, name='registration_success'),
]
