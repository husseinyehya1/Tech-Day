
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path

from students import views as student_views

from dashboard import views as dashboard_views

from users import views as users_views

def redirect_to_login(request):
    return redirect('users:login')

urlpatterns = [
    path('td/<str:identifier>/', student_views.student_verify, name='student_verify'),
    path('admin/', admin.site.urls),
    path('login/', redirect_to_login),
    path('change_password/', users_views.change_password, name='change_password_root'),
    path('dashboard/', dashboard_views.admin_dashboard, name='dashboard'),
    path('حساب/', include('users.urls')),
    path('طلاب/', include('students.urls')),
    path('مجموعات/', include('groups.urls')),
    path('ورش/', include('workshops.urls')),
    path('حضور/', include('attendance.urls')),
    path('لوحة/', include('dashboard.urls')),
    path('api/', include('api.urls')),
    re_path(r'^media/(?P<file_path>.+)$', dashboard_views.media_proxy, name='media_proxy'),
    path('', include('public_screen.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
