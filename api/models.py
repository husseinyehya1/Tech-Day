from django.db import models
from django.conf import settings
from django.utils import timezone

class MobileDevice(models.Model):
    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    device_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mobile_devices',
    )
    fcm_device_id = models.IntegerField(null=True, blank=True)
    platform = models.CharField(max_length=20, choices=Platform.choices, blank=True, default='')
    name = models.CharField(max_length=200, blank=True, default='')
    app_version = models.CharField(max_length=50, blank=True, default='')
    build_number = models.PositiveIntegerField(null=True, blank=True)
    device_model = models.CharField(max_length=200, blank=True, default='')
    manufacturer = models.CharField(max_length=200, blank=True, default='')
    os_version = models.CharField(max_length=100, blank=True, default='')
    battery_level = models.PositiveIntegerField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    is_banned = models.BooleanField(default=False)
    banned_reason = models.TextField(blank=True, default='')
    banned_at = models.DateTimeField(null=True, blank=True)
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banned_mobile_devices',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.device_id}'
