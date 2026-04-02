from django.contrib import admin
from django.utils import timezone
from fcm_django.models import FCMDevice

from .models import MobileDevice

@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'device_id',
        'user',
        'platform',
        'name',
        'app_version',
        'build_number',
        'device_model',
        'os_version',
        'battery_level',
        'is_banned',
        'last_seen_at',
    )
    list_filter = ('platform', 'is_banned')
    search_fields = ('device_id', 'name', 'device_model', 'manufacturer', 'os_version', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'last_seen_at')
    actions = ('ban_devices', 'unban_devices')

    def ban_devices(self, request, queryset):
        now = timezone.localtime()
        updated = queryset.update(is_banned=True, banned_at=now, banned_by=request.user)
        fcm_ids = list(queryset.exclude(fcm_device_id__isnull=True).values_list('fcm_device_id', flat=True))
        if fcm_ids:
            FCMDevice.objects.filter(id__in=fcm_ids).update(active=False)
        self.message_user(request, f'تم حظر {updated} جهاز.')

    def unban_devices(self, request, queryset):
        updated = queryset.update(is_banned=False, banned_at=None, banned_by=None, banned_reason='')
        fcm_ids = list(queryset.exclude(fcm_device_id__isnull=True).values_list('fcm_device_id', flat=True))
        if fcm_ids:
            FCMDevice.objects.filter(id__in=fcm_ids).update(active=True)
        self.message_user(request, f'تم إلغاء حظر {updated} جهاز.')
