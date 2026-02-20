from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'student_id', 'group', 'school')
    list_filter = ('group',)
    search_fields = ('name', 'student_id', 'school')
