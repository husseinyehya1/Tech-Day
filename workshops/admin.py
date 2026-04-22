from django.contrib import admin

from .models import Workshop, WorkshopSession


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'supervisor', 'status')
    list_filter = ('status',)
    search_fields = ('title', 'room')


@admin.register(WorkshopSession)
class WorkshopSessionAdmin(admin.ModelAdmin):
    list_display = ('workshop', 'group', 'period', 'start_time', 'end_time')
    list_filter = ('period', 'group')
