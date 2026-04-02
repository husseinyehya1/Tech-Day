from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views


router = DefaultRouter()
router.register(r'students', views.StudentViewSet)
router.register(r'events', views.EventViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'workshops', views.WorkshopViewSet)
router.register(r'sessions', views.WorkshopSessionViewSet)
router.register(r'attendance', views.AttendanceViewSet)
router.register(r'feedback', views.WorkshopFeedbackViewSet)
router.register(r'notes', views.StudentWorkshopNoteViewSet)
router.register(r'resources', views.WorkshopResourceViewSet)
router.register(r'notifications', views.NotificationViewSet)
router.register(r'sos-requests', views.SOSRequestViewSet)
router.register(r'support-requests', views.StudentSupportRequestViewSet)
router.register(r'registrations', views.StudentRegistrationViewSet)
router.register(r'volunteer-notes', views.VolunteerNoteViewSet)
router.register(r'failed-emails', views.FailedEmailViewSet)
router.register(r'vip-invites', views.VIPInviteViewSet)
router.register(r'violations', views.StudentViolationViewSet)
router.register(r'admin-logs', views.AdminLogViewSet)

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('app-version/', views.CheckAppVersionView.as_view(), name='app_version'),
    path('dashboard/api/app-version/', views.CheckAppVersionView.as_view(), name='legacy_app_version'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('admin/kpis/', views.AdminKPIsView.as_view(), name='admin_kpis'),
    path('admin/broadcast/', views.BroadcastView.as_view(), name='broadcast_api'),
    path('admin/search-students/', views.StudentSearchView.as_view(), name='search_students_api'),
    path('students/award-points/', views.AwardPointsView.as_view(), name='award_points_api'),
    path('devices/', views.RegisterDeviceView.as_view(), name='create_fcm_device'),
    path('', include(router.urls)),
]
