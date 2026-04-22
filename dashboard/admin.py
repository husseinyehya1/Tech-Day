from django.contrib import admin
from .models import (
    AdminLog, Notification, Event, VIPInvite, 
    VolunteerNote, SOSRequest, BroadcastMessage, 
    FailedEmail, StudentViolation, StudentSupportRequest,
    AppVersion
)

@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ('platform', 'version_code', 'build_number', 'min_build_number', 'is_force_update', 'apk_file', 'created_at')
    list_filter = ('platform', 'is_force_update')
    search_fields = ('version_code', 'build_number')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'location_name', 'execution_number', 'is_active', 'is_finished')
    list_filter = ('is_active', 'is_finished', 'year')
    search_fields = ('name', 'location_name')

@admin.register(StudentSupportRequest)
class StudentSupportRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'subject', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('student__name', 'subject')

admin.site.register(AdminLog)
admin.site.register(Notification)
admin.site.register(VIPInvite)
admin.site.register(VolunteerNote)
admin.site.register(SOSRequest)
admin.site.register(BroadcastMessage)
admin.site.register(FailedEmail)
admin.site.register(StudentViolation)
