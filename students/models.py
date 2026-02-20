from django.conf import settings
from django.db import models

from groups.models import Group


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profile',
        verbose_name='حساب المستخدم',
    )
    name = models.CharField(max_length=150, verbose_name='اسم الطالب')
    student_id = models.CharField(max_length=20, unique=True, verbose_name='رقم الطالب')
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name='المجموعة',
    )
    school = models.CharField(max_length=150, blank=True, verbose_name='المدرسة')
    education_admin = models.CharField(max_length=150, blank=True, verbose_name='الإدارة التعليمية')
    email = models.EmailField(max_length=254, blank=True, verbose_name='البريد الإلكتروني')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    checked_in = models.BooleanField(default=False, verbose_name='تم تسجيل دخول الفعالية')
    checked_in_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت تسجيل الدخول للفعالية')

    class Meta:
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'

    def __str__(self):
        return f'{self.name} ({self.student_id})'
