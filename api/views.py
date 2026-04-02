from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from students.models import Student, StudentRegistration, StudentWorkshopNote
from groups.models import Group
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback, WorkshopResource
from dashboard.models import (
    Event, Notification, SOSRequest, StudentSupportRequest, 
    VolunteerNote, FailedEmail, BroadcastMessage, VIPInvite, 
    StudentViolation, AdminLog, AppVersion
)
from attendance.models import Attendance
from students.utils import check_and_award_badges
from students.models import StudentEventStats
from users.models import User

from .serializers import (
    UserSerializer, StudentSerializer, GroupSerializer, 
    EventSerializer, WorkshopSerializer, WorkshopSessionSerializer,
    AttendanceSerializer, WorkshopFeedbackSerializer, NotificationSerializer,
    StudentRegistrationSerializer, StudentWorkshopNoteSerializer, WorkshopResourceSerializer,
    SOSRequestSerializer, StudentSupportRequestSerializer,
    VolunteerNoteSerializer, FailedEmailSerializer, VIPInviteSerializer,
    StudentViolationSerializer, AdminLogSerializer
)
from fcm_django.models import FCMDevice

from .models import MobileDevice


class CheckAppVersionView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        platform = (request.GET.get('platform') or 'android').lower()
        try:
            current_build = int(request.GET.get('build', 0))
        except (ValueError, TypeError):
            current_build = 0

        latest_version = AppVersion.objects.filter(platform=platform).order_by('-build_number').first()
        if not latest_version:
            return Response({'update_required': False, 'update_available': False})

        update_available = latest_version.build_number > current_build
        update_required = (
            latest_version.min_build_number > current_build
            or (latest_version.is_force_update and update_available)
        )

        download_url = latest_version.download_url
        if not download_url and latest_version.apk_file:
            download_url = request.build_absolute_uri(latest_version.apk_file.url)

        return Response(
            {
                'update_available': update_available,
                'update_required': update_required,
                'is_force_update': latest_version.is_force_update and update_available,
                'latest_version': latest_version.version_code,
                'latest_build': latest_version.build_number,
                'download_url': download_url,
                'release_notes': latest_version.release_notes,
            }
        )

class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def current(self, request):
        cache_key = 'current_event_api'
        data = cache.get(cache_key)
        
        if not data:
            event = Event.get_current()
            if not event:
                return Response({"error": "No current event"}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = self.get_serializer(event)
            data = serializer.data
            
            # Add maintenance info for the mobile app
            data['is_maintenance_mode'] = event.is_maintenance_mode
            data['maintenance_facebook_url'] = event.maintenance_facebook_url
            cache.set(cache_key, data, 60) # Cache for 1 minute
        
        return Response(data)

    def get_queryset(self):
        return Event.objects.filter(is_active=True)

class MaintenancePermission(permissions.BasePermission):
    """
    Global permission check for maintenance mode.
    """
    def has_permission(self, request, view):
        event = Event.get_current()
        if event and event.is_maintenance_mode:
            # Allow admins to bypass maintenance
            if request.user.is_authenticated:
                if request.user.role == 'admin' or request.user.is_superuser:
                    return True
            
            # Maintenance mode is ON, deny access for others
            from rest_framework.exceptions import APIException
            from rest_framework import status
            
            class MaintenanceModeException(APIException):
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                default_detail = 'النظام حالياً تحت الصيانة. يرجى المحاولة لاحقاً.'
                default_code = 'maintenance_mode'
                
                def __init__(self, facebook_url):
                    self.detail = {
                        'error': 'maintenance_mode',
                        'message': self.default_detail,
                        'facebook_url': facebook_url
                    }

            raise MaintenanceModeException(event.maintenance_facebook_url)
        return True


class RegisterDeviceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        registration_id = (request.data.get('registration_id') or '').strip()
        device_type = (request.data.get('type') or '').strip().lower()
        device_id = (request.data.get('device_id') or '').strip()
        name = (request.data.get('name') or '').strip()
        metadata = request.data.get('metadata') or {}

        if device_type not in {MobileDevice.Platform.ANDROID, MobileDevice.Platform.IOS}:
            device_type = MobileDevice.Platform.ANDROID
        if not device_id:
            device_id = registration_id
        if not device_id:
            return Response({'detail': 'device_id مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            mobile, _ = MobileDevice.objects.select_for_update().get_or_create(device_id=device_id)
            if mobile.is_banned:
                if mobile.fcm_device_id:
                    FCMDevice.objects.filter(id=mobile.fcm_device_id).update(active=False)
                return Response(
                    {'detail': 'هذا الجهاز محظور.', 'device_id': device_id, 'is_banned': True},
                    status=status.HTTP_403_FORBIDDEN,
                )

            fcm_device = None
            if registration_id:
                fcm_device = FCMDevice.objects.filter(device_id=device_id).first()
                if not fcm_device and settings.FCM_DJANGO_SETTINGS.get('ONE_DEVICE_PER_USER'):
                    fcm_device = FCMDevice.objects.filter(user=request.user).first()

                if fcm_device:
                    fcm_device.user = request.user
                    fcm_device.registration_id = registration_id
                    fcm_device.type = device_type
                    fcm_device.device_id = device_id
                    fcm_device.active = True
                    if name:
                        fcm_device.name = name[:200]
                    fcm_device.save()
                else:
                    fcm_device = FCMDevice.objects.create(
                        user=request.user,
                        registration_id=registration_id,
                        type=device_type,
                        device_id=device_id,
                        active=True,
                        name=name[:200] if name else '',
                    )

                FCMDevice.objects.filter(registration_id=registration_id).exclude(pk=fcm_device.pk).update(active=False)
            elif mobile.fcm_device_id:
                fcm_device = FCMDevice.objects.filter(id=mobile.fcm_device_id).first()

            mobile.user = request.user
            mobile.platform = device_type
            if fcm_device:
                mobile.fcm_device_id = fcm_device.id
            if name:
                mobile.name = name[:200]
            mobile.app_version = str(metadata.get('app_version') or '')[:50]
            build_number = metadata.get('build_number')
            if isinstance(build_number, int):
                mobile.build_number = build_number
            mobile.device_model = str(metadata.get('device_model') or '')[:200]
            mobile.manufacturer = str(metadata.get('manufacturer') or '')[:200]
            mobile.os_version = str(metadata.get('os_version') or '')[:100]
            battery_level = metadata.get('battery_level')
            if isinstance(battery_level, int) and 0 <= battery_level <= 100:
                mobile.battery_level = battery_level
            mobile.last_seen_at = timezone.now()
            mobile.save()

        return Response(
            {'success': True, 'device_id': device_id, 'fcm_device_id': fcm_device.id if fcm_device else None},
            status=status.HTTP_200_OK,
        )

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_object(self):
        return self.request.user

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by('-points', 'name')
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            student = Student.objects.select_related('group', 'group__event').get(user=request.user)
            serializer = self.get_serializer(student)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response({"error": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def get_queryset(self):
        qs = Student.objects.all()
        q = self.request.query_params.get('q')
        group_id = self.request.query_params.get('group') or self.request.query_params.get('group_id')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(student_id__icontains=q) | Q(school__icontains=q)
            )
        if group_id:
            qs = qs.filter(group_id=group_id)

        # Apply ordering and limit for leaderboard if requested
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
                return qs.order_by('-points', 'name')[:limit]
            except ValueError:
                pass

        return qs.order_by('-points', 'name')

    def update(self, request, *args, **kwargs):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy()
        group_id = data.pop('group', None)
        if group_id:
            try:
                instance.group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                return Response({"error": "group_not_found"}, status=status.HTTP_400_BAD_REQUEST)
        allowed_fields = ['name', 'school', 'education_admin', 'grade', 'email', 'phone_number']
        for f in allowed_fields:
            if f in data:
                setattr(instance, f, data.get(f))
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role not in ['admin']:
            raise PermissionDenied()
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='update-phone')
    def update_phone(self, request):
        phone = (request.data.get('phone_number') or '').strip()
        if not phone:
            return Response({"error": "phone_number is required"}, status=status.HTTP_400_BAD_REQUEST)
        # Basic Egyptian mobile validation
        import re
        if not re.match(r'^01(0|1|2|5)\d{8}$', phone):
            return Response({"error": "invalid_phone_format"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            return Response({"error": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)
        student.phone_number = phone
        student.save()
        return Response({"success": True, "phone_number": student.phone_number})

class ChangePasswordView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        old_password = (request.data.get('old_password') or '').strip()
        new_password = (request.data.get('new_password') or '').strip()
        if not old_password or not new_password:
            return Response({"error": "old_password and new_password are required"}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if not user.check_password(old_password):
            return Response({"error": "invalid_old_password"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({"success": True})

from techday.utils import send_email_async, get_styled_email_html

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def current(self, request):
        event = Event.get_current()
        serializer = self.get_serializer(event)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='update-settings')
    def update_settings(self, request):
        if request.user.role != 'admin':
            raise PermissionDenied()
        
        event = Event.get_current()
        data = request.data
        
        start_date = data.get('start_date')
        start_time = data.get('start_time')
        
        if start_date and start_time:
            try:
                from datetime import datetime
                naive = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
                event.start_datetime = timezone.make_aware(naive, timezone.get_current_timezone())
            except ValueError:
                return Response({"error": "Invalid date or time format"}, status=status.HTTP_400_BAD_REQUEST)
        
        event.location_name = data.get('location_name', event.location_name)
        event.location_link = data.get('location_link', event.location_link)
        event.arrival_time_text = data.get('arrival_time_text', event.arrival_time_text)
        event.whatsapp_group_link = data.get('whatsapp_group_link', event.whatsapp_group_link)
        event.event_instructions = data.get('event_instructions', event.event_instructions)
        
        max_students = data.get('max_students')
        if max_students is not None:
            try:
                event.max_students = int(max_students)
            except (ValueError, TypeError):
                pass
                
        event.save()
        return Response(self.get_serializer(event).data)

    @action(detail=False, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request):
        if request.user.role != 'admin':
            raise PermissionDenied()
        
        event = Event.get_current()
        action = request.data.get('action')
        
        if action == 'end':
            Workshop.objects.exclude(status='finished').update(status='finished')
            event.is_finished = True
            event.save(update_fields=['is_finished'])
            from dashboard.models import AdminLog
            AdminLog.objects.create(action='تم إنهاء الفعالية من التطبيق', event=event)
            return Response({"success": True, "status": "finished"})
        elif action == 'resume':
            event.is_finished = False
            event.save(update_fields=['is_finished'])
            from dashboard.models import AdminLog
            AdminLog.objects.create(action='تم استئناف الفعالية من التطبيق', event=event)
            return Response({"success": True, "status": "active"})
            
        return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='send-mass-email')
    def send_mass_email(self, request):
        if request.user.role != 'admin':
            raise PermissionDenied()
            
        type = request.data.get('type')
        event = Event.get_current()
        students = Student.objects.filter(email__isnull=False).exclude(email='')
        
        if not students.exists():
            return Response({"error": "No students with email found"}, status=status.HTTP_400_BAD_REQUEST)
            
        count = 0
        from techday.utils import send_email_async, get_styled_email_html
        
        for student in students:
            subject = ""
            title = ""
            main_text = ""
            content_blocks = ""
            
            if type == 'location':
                if not event.location_name or not event.location_link:
                    return Response({"error": "Location info missing"}, status=status.HTTP_400_BAD_REQUEST)
                
                subject = f'تأكيد حضور فعالية {event.name} - الموقع والموعد'
                title = "✅ تأكيد حضور الفعالية"
                main_text = f"مرحبًا {student.name}، يسعدنا تأكيد حضورك لفعالية <b>{event.name}</b>."
                
                arrival_time = event.arrival_time_text or (event.start_datetime.strftime('%I:%M %p') if event.start_datetime else '8:00 AM')
                date_str = event.start_datetime.strftime('%Y-%m-%d') if event.start_datetime else 'يوم الفعالية'
                
                content_blocks = f"""
                    <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #1e293b;margin-bottom:20px;">
                      <p class="td-email-text-main" style="margin:0 0 20px;font-size:15px;color:#22d3ee;font-weight:700;text-align:center;">📍 تفاصيل الحضور والموقع</p>
                      <div style="background:#1e293b;border-radius:16px;padding:16px;margin-bottom:16px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="direction:rtl;text-align:right;">
                          <tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;width:100px;">📅 التاريخ</td><td style="padding:8px 0;font-size:14px;color:#e5e7eb;font-weight:600;">{date_str}</td></tr>
                          <tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;">⏰ وقت الحضور</td><td style="padding:8px 0;font-size:14px;color:#f97316;font-weight:700;">{arrival_time}</td></tr>
                          <tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;">📍 المكان</td><td style="padding:8px 0;font-size:14px;color:#e5e7eb;font-weight:600;">{event.location_name}</td></tr>
                        </table>
                      </div>
                      <div style="text-align:center;">
                        <a href="{event.location_link}" style="display:inline-block;padding:14px 32px;border-radius:999px;background-color:#22d3ee;color:#0f172a;font-size:15px;font-weight:700;text-decoration:none;">🗺️ فتح الموقع على الخريطة</a>
                      </div>
                    </div>
                """
            
            elif type == 'whatsapp':
                if not event.whatsapp_group_link:
                    return Response({"error": "WhatsApp link missing"}, status=status.HTTP_400_BAD_REQUEST)
                
                subject = f'رابط مجموعة الواتساب لفعالية {event.name}'
                title = "💬 انضم لمجموعة الواتساب"
                main_text = f"مرحبًا {student.name}، يرجى الانضمام لمجموعة الواتساب الرسمية للفعالية لمتابعة التحديثات."
                content_blocks = f"""
                    <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #25d366;text-align:center;">
                      <a href="{event.whatsapp_group_link}" style="display:inline-block;padding:14px 32px;border-radius:999px;background-color:#25d366;color:#ffffff;font-size:15px;font-weight:700;text-decoration:none;">الانضمام للمجموعة</a>
                    </div>
                """
                
            elif type == 'instructions':
                if not event.event_instructions:
                    return Response({"error": "Instructions missing"}, status=status.HTTP_400_BAD_REQUEST)
                
                subject = f'تعليمات هامة لفعالية {event.name}'
                title = "📋 تعليمات الفعالية"
                main_text = f"مرحبًا {student.name}، يرجى قراءة التعليمات التالية بعناية قبل الحضور."
                content_blocks = f"""
                    <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #1e293b;text-align:right;direction:rtl;">
                      <div style="color:#e5e7eb;font-size:14px;line-height:1.6;">{event.event_instructions.replace('\n', '<br>')}</div>
                    </div>
                """
            
            if subject:
                html_body = get_styled_email_html(
                    subject=subject,
                    preview_text=subject,
                    title=title,
                    main_text=main_text,
                    content_blocks_html=content_blocks
                )
                send_email_async(subject, student.email, html_body)
                count += 1
                
        return Response({"success": True, "sent_count": count})

class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return Group.objects.filter(event_id=event_id)
        return Group.objects.all()

class WorkshopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Workshop.objects.all()
    serializer_class = WorkshopSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return Workshop.objects.filter(event_id=event_id)
        return Workshop.objects.all()

class WorkshopSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkshopSession.objects.all()
    serializer_class = WorkshopSessionSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        workshop_id = self.request.query_params.get('workshop_id')
        group_id = self.request.query_params.get('group_id')
        
        # If no group_id is provided and user is a student, use their group
        if not group_id and self.request.user.role == 'student':
            try:
                student = Student.objects.only('group_id').get(user=self.request.user)
                group_id = student.group_id
            except Student.DoesNotExist:
                pass

        queryset = WorkshopSession.objects.select_related('workshop', 'group').all()
        if workshop_id:
            queryset = queryset.filter(workshop_id=workshop_id)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        return queryset.order_by('period', 'start_time')

class StudentRegistrationViewSet(viewsets.ModelViewSet):
    queryset = StudentRegistration.objects.all().order_by('-created_at')
    serializer_class = StudentRegistrationSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            # Registration creation might be allowed even in maintenance if it's external,
            # but usually maintenance means "stop everything". Let's apply MaintenancePermission.
            return [permissions.AllowAny(), MaintenancePermission()]
        return [permissions.IsAuthenticated(), MaintenancePermission()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role in ['admin', 'supervisor']:
            event = Event.get_current()
            status_filter = self.request.query_params.get('status')
            queryset = StudentRegistration.objects.filter(event=event)
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            return queryset.order_by('-created_at')
        return super().get_queryset()

    def perform_create(self, serializer):
        event = Event.get_current()
        serializer.save(event=event)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        
        reg = self.get_object()
        if reg.status == StudentRegistration.Status.APPROVED:
            return Response({"error": "Already approved"}, status=status.HTTP_400_BAD_REQUEST)
        
        # logic from dashboard/views.py:admin_approve_registration
        from django.utils import timezone
        import random
        import string
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # 1. Create/Update Student
        student, created = Student.objects.get_or_create(
            student_id=reg.phone_number[-8:], # common pattern in this project
            defaults={
                'name': reg.full_name_ar,
                'email': reg.email,
                'phone_number': reg.phone_number,
                'school': reg.school,
                'education_admin': reg.education_admin,
                'grade': reg.grade,
            }
        )
        
        # 2. Create User account if not exists
        if not student.user:
            username = reg.phone_number
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user = User.objects.create_user(
                username=username,
                email=reg.email,
                password=password,
                role='student',
                first_name=reg.full_name_ar.split()[0] if reg.full_name_ar else "",
            )
            student.user = user
            student.save()
            
            # Send welcome email (async)
            from techday.utils import send_email_async, get_styled_email_html
            subject = f"تم قبول تسجيلك في {reg.event.name}"
            html = get_styled_email_html(
                subject=subject,
                preview_text="بيانات دخولك للنظام",
                title="🎉 تم قبول طلبك بنجاح",
                main_text=f"مرحبًا {reg.full_name_ar}، يسعدنا إبلاغك بقبول تسجيلك في الفعالية.",
                content_blocks_html=f"""
                    <div style="background:#1e293b;padding:20px;border-radius:12px;margin:20px 0;text-align:center;">
                        <p style="color:#94a3b8;margin:0 0 10px;">بيانات تسجيل الدخول:</p>
                        <p style="color:#ffffff;font-size:18px;font-weight:700;margin:5px 0;">اسم المستخدم: {username}</p>
                        <p style="color:#ffffff;font-size:18px;font-weight:700;margin:5px 0;">كلمة المرور: {password}</p>
                    </div>
                """
            )
            send_email_async(subject, reg.email, html)

        reg.status = StudentRegistration.Status.APPROVED
        reg.student = student
        reg.approved_by = request.user
        reg.approved_at = timezone.now()
        reg.save()
        
        return Response({"success": True})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        
        reg = self.get_object()
        reg.status = StudentRegistration.Status.REJECTED
        reg.save()
        return Response({"success": True})

class StudentSupportRequestViewSet(viewsets.ModelViewSet):
    queryset = StudentSupportRequest.objects.all()
    serializer_class = StudentSupportRequestSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'student':
            try:
                student = Student.objects.get(user=user)
                return StudentSupportRequest.objects.filter(student=student)
            except Student.DoesNotExist:
                return StudentSupportRequest.objects.none()
        elif user.role == 'supervisor' or user.role == 'admin':
            return StudentSupportRequest.objects.all()
        return StudentSupportRequest.objects.none()

    def perform_create(self, serializer):
        event = Event.get_current()
        serializer.save(event=event)

    def update(self, request, *args, **kwargs):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        return super().partial_update(request, *args, **kwargs)

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        student_id = self.request.query_params.get('student_id')
        if student_id:
            return Attendance.objects.filter(student_id=student_id)
        return Attendance.objects.all()

    def perform_create(self, serializer):
        serializer.save(scanned_at=timezone.now())

class WorkshopFeedbackViewSet(viewsets.ModelViewSet):
    queryset = WorkshopFeedback.objects.all()
    serializer_class = WorkshopFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'student':
            try:
                student = Student.objects.get(user=user)
                return WorkshopFeedback.objects.filter(student=student)
            except Student.DoesNotExist:
                return WorkshopFeedback.objects.none()
        
        student_id = self.request.query_params.get('student_id')
        if student_id:
            return WorkshopFeedback.objects.filter(student_id=student_id)
        return WorkshopFeedback.objects.all()

class StudentWorkshopNoteViewSet(viewsets.ModelViewSet):
    queryset = StudentWorkshopNote.objects.all()
    serializer_class = StudentWorkshopNoteSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'student':
            try:
                student = Student.objects.get(user=user)
                return StudentWorkshopNote.objects.filter(student=student)
            except Student.DoesNotExist:
                return StudentWorkshopNote.objects.none()

        student_id = self.request.query_params.get('student_id')
        if student_id:
            return StudentWorkshopNote.objects.filter(student_id=student_id)
        return StudentWorkshopNote.objects.all()

class WorkshopResourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkshopResource.objects.all()
    serializer_class = WorkshopResourceSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        workshop_id = self.request.query_params.get('workshop_id')
        if workshop_id:
            return WorkshopResource.objects.filter(workshop_id=workshop_id)
        return WorkshopResource.objects.all()

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.filter(is_active=True)
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        return Notification.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        return super().create(request, *args, **kwargs)

class SOSRequestViewSet(viewsets.ModelViewSet):
    queryset = SOSRequest.objects.all()
    serializer_class = SOSRequestSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'student':
            try:
                student = Student.objects.get(user=user)
                return SOSRequest.objects.filter(student=student)
            except Student.DoesNotExist:
                return SOSRequest.objects.none()
        elif user.role == 'supervisor' or user.role == 'admin':
            return SOSRequest.objects.all().order_by('-created_at')
        return SOSRequest.objects.none()

    def perform_create(self, serializer):
        event = Event.get_current()
        serializer.save(event=event)

class VolunteerNoteViewSet(viewsets.ModelViewSet):
    queryset = VolunteerNote.objects.all().order_by('-created_at')
    serializer_class = VolunteerNoteSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        if self.request.user.role not in ['admin', 'supervisor']:
            return VolunteerNote.objects.none()
        return VolunteerNote.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class FailedEmailViewSet(viewsets.ModelViewSet):
    queryset = FailedEmail.objects.all().order_by('-created_at')
    serializer_class = FailedEmailSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return FailedEmail.objects.none()
        return FailedEmail.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        if request.user.role != 'admin':
            raise PermissionDenied()
        email_obj = self.get_object()
        from techday.utils import send_email_async
        send_email_async(email_obj.subject, email_obj.recipient, email_obj.html_content)
        email_obj.attempts += 1
        email_obj.last_attempt = timezone.now()
        email_obj.save()
        return Response({'status': 'retrying'})

class VIPInviteViewSet(viewsets.ModelViewSet):
    queryset = VIPInvite.objects.all().order_by('-created_at')
    serializer_class = VIPInviteSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return VIPInvite.objects.none()
        return VIPInvite.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        event = Event.get_current()
        serializer.save(event=event, created_by=self.request.user)

class StudentViolationViewSet(viewsets.ModelViewSet):
    queryset = StudentViolation.objects.all().order_by('-created_at')
    serializer_class = StudentViolationSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        if self.request.user.role not in ['admin', 'supervisor']:
            return StudentViolation.objects.none()
        return StudentViolation.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        event = Event.get_current()
        serializer.save(event=event, reported_by=self.request.user)

class AdminLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AdminLog.objects.all().order_by('-created_at')
    serializer_class = AdminLogSerializer
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return AdminLog.objects.none()
        return AdminLog.objects.all().order_by('-created_at')

class AdminKPIsView(APIView):
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get(self, request):
        user = request.user
        if user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
            
        event = Event.get_current()
        now = timezone.localtime()
        today = now.date()
        
        # Statistics matching dashboard/views.py:admin_dashboard
        total_students = StudentRegistration.objects.filter(
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).count()
        total_present = Student.objects.filter(checked_in=True).count()
        
        students_with_accounts = Student.objects.filter(user__isnull=False).count()
        total_logins_ever = Student.objects.filter(user__last_login__isnull=False).count()
        total_logins_today = Student.objects.filter(user__last_login__date=today).count()
        
        active_workshops = Workshop.objects.filter(event=event, status='active').count()
        pending_emails_count = FailedEmail.objects.count()
        today_notes_count = VolunteerNote.objects.filter(created_at__date=today).count()
        
        open_support = StudentSupportRequest.objects.filter(status__in=['pending', 'in_progress']).count()
        sessions_count = WorkshopSession.objects.filter(workshop__event=event).count()
        notifs_today = Notification.objects.filter(event=event, created_at__date=today).count()
        groups_count = Group.objects.filter(event=event).count()

        event_status = 'لم تبدأ بعد'
        if event.is_finished:
            event_status = 'متوقفة'
        elif event.start_datetime:
            if now < event.start_datetime:
                event_status = 'لم تبدأ بعد'
            elif now >= event.start_datetime:
                event_status = 'جارية'

        return Response({
            "total_students": total_students,
            "total_present": total_present,
            "students_with_accounts": students_with_accounts,
            "total_logins_ever": total_logins_ever,
            "total_logins_today": total_logins_today,
            "active_workshops": active_workshops,
            "pending_emails_count": pending_emails_count,
            "today_notes_count": today_notes_count,
            "event_status": event_status,
            "open_support_requests": open_support,
            "sessions_count": sessions_count,
            "notifications_today": notifs_today,
            "groups_count": groups_count,
        })

class BroadcastView(APIView):
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def post(self, request):
        if request.user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        
        message = (request.data.get('message') or '').strip()
        target = request.data.get('target', 'all')
        duration = int(request.data.get('duration') or 5)
        
        if not message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        expires_at = timezone.now() + timezone.timedelta(minutes=duration)
        
        # Deactivate previous active broadcasts for the same target
        BroadcastMessage.objects.filter(target=target, is_active=True).update(is_active=False)
        
        BroadcastMessage.objects.create(
            event=Event.get_current(),
            author=request.user,
            message=message,
            target=target,
            expires_at=expires_at
        )
        return Response({"success": True})

    def get(self, request):
        now = timezone.now()
        user_target = 'all'
        if hasattr(request.user, 'role'):
            if request.user.role == 'supervisor':
                user_target = 'supervisors'
            elif request.user.role == 'volunteer':
                user_target = 'volunteers'
        
        if not hasattr(request.user, 'role') or request.user.role == 'student':
            if Student.objects.filter(user=request.user).exists():
                user_target = 'students'

        broadcasts = BroadcastMessage.objects.filter(
            Q(target='all') | Q(target=user_target),
            is_active=True,
            expires_at__gt=now
        ).order_by('-created_at')
        
        data = []
        for b in broadcasts:
            data.append({
                'id': b.id,
                'message': b.message,
                'target': b.get_target_display(),
                'type': b.target,
                'author': b.author.username,
                'created_at': b.created_at
            })
        return Response(data)

class AwardPointsView(APIView):
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def post(self, request):
        user = request.user
        if user.role not in ['admin', 'supervisor']:
            raise PermissionDenied()
        event = Event.get_current()
        student_identifier = (request.data.get('student_id') or '').strip()
        points = int(request.data.get('points') or 0)
        reason = (request.data.get('reason') or 'مكافأة سريعة').strip()

        if not student_identifier or points == 0:
            return Response({"error": "student_id and non-zero points are required"}, status=status.HTTP_400_BAD_REQUEST)

        # If group points not allowed, restrict non-admin users
        if event and not event.allow_group_points and user.role != 'admin':
            return Response({"error": "group points are disabled by admins currently"}, status=status.HTTP_403_FORBIDDEN)

        student = get_object_or_404(Student, student_id=student_identifier)
        # Ensure student registered in current event
        is_registered = StudentRegistration.objects.filter(
            student=student,
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()
        if not is_registered:
            return Response({"error": "student not registered/approved for current event"}, status=status.HTTP_400_BAD_REQUEST)

        # Update student & event stats
        if points != 0:
            student.points += points
            student.save(update_fields=['points'])

            stats, _ = StudentEventStats.objects.get_or_create(student=student, event=event)
            stats.points += points
            stats.save(update_fields=['points'])

            # Group points only if allowed and same event
            if student.group and student.group.event == event and event.allow_group_points:
                student.group.points += points
                student.group.save(update_fields=['points'])

            # Check badges
            check_and_award_badges(student, event=event)

            # Optional: log action (if AdminLog available)
            # AdminLog.objects.create(action=f'Awarded {points} points to {student.name} by {user.username}. Reason: {reason}', event=event)

        return Response({"success": True, "student": student.id, "points": points, "reason": reason})

class StudentSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated, MaintenancePermission]

    def get(self, request):
        user = request.user
        if user.role not in ['admin', 'supervisor', 'volunteer']:
            raise PermissionDenied()
        
        query = request.GET.get('q', '').strip()
        if not query:
            return Response([])
        
        event = Event.get_current()
        students = Student.objects.filter(
            Q(name__icontains=query) | Q(student_id__icontains=query),
            registrations__event=event,
            registrations__status=StudentRegistration.Status.APPROVED,
            registrations__removed_at__isnull=True,
        ).select_related('group').distinct()[:15]
        
        results = []
        for s in students:
            results.append({
                'id': s.id,
                'student_id': s.student_id,
                'name': s.name,
                'group_code': s.group.code if s.group and s.group.event == event else 'بدون مجموعة',
                'school': s.school or 'بدون مدرسة'
            })
        
        return Response(results)
