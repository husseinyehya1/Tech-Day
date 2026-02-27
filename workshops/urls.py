from django.urls import path
from . import views

app_name = 'workshops'

urlpatterns = [
    path('', views.workshop_list, name='list'),
    path('feedback/', views.student_submit_feedback, name='submit_feedback'),
]
