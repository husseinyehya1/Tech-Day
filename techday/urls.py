"""
URL configuration for techday project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

from students import views as student_views

from dashboard import views as dashboard_views

def redirect_to_login(request):
    return redirect('users:login')

urlpatterns = [
    path('td/<str:identifier>/', student_views.student_verify, name='student_verify'),
    path('admin/', admin.site.urls),
    path('login/', redirect_to_login),
    path('dashboard/', dashboard_views.admin_dashboard, name='dashboard'),
    path('حساب/', include('users.urls')),
    path('طلاب/', include('students.urls')),
    path('مجموعات/', include('groups.urls')),
    path('ورش/', include('workshops.urls')),
    path('حضور/', include('attendance.urls')),
    path('لوحة/', include('dashboard.urls')),
    path('', include('public_screen.urls')),
]
