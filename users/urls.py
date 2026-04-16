from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('تسجيل-دخول/', views.login_view, name='login'),
    path('تسجيل-خروج/', views.logout_view, name='logout'),
    path('تغيير-كلمة-المرور/', views.change_password, name='change_password'),
    path('change_password/', views.change_password, name='change_password_en'),
]
