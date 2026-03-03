from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'status', 'scanned_at')
    list_filter = ('status', 'session__workshop', 'session__group')
    search_fields = ('student__name', 'student__student_id')
