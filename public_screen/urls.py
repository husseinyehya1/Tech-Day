from django.urls import path
from . import views

app_name = 'public_screen'

urlpatterns = [
    path('', views.public_screen_view, name='public_screen'),
]
