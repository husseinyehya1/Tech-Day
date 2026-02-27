from django.conf import settings
from django.db import models

from students.models import Student


class AdminLog(models.Model):
    action = models.CharField(max_length=255, verbose_name='الإجراء')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')

    class Meta:
        verbose_name = 'سجل إدارة'
        verbose_name_plural = 'سجلات الإدارة'
        ordering = ['-created_at']

    def __str__(self):
        return self.action


class Notification(models.Model):
    class Target(models.TextChoices):
        ALL = 'all', 'كل الطلاب'
        GROUP = 'group', 'مجموعة معينة'
        SUPERVISORS = 'supervisors', 'المشرفون'

    title = models.CharField(max_length=200, verbose_name='العنوان')
    body = models.TextField(verbose_name='النص')
    target = models.CharField(
        max_length=20,
        choices=Target.choices,
        default=Target.ALL,
        verbose_name='الفئة المستهدفة',
    )
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='المجموعة',
    )
    is_active = models.BooleanField(default=True, verbose_name='مفعّل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')

    class Meta:
        verbose_name = 'تنبيه'
        verbose_name_plural = 'التنبيهات'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class EventSettings(models.Model):
    name = models.CharField(max_length=150, default='Tech Day', verbose_name='اسم الفعالية')
    start_datetime = models.DateTimeField(null=True, blank=True, verbose_name='موعد بدء الفعالية')
    location_name = models.CharField(max_length=255, blank=True, verbose_name='مكان الفعالية')
    location_link = models.URLField(blank=True, verbose_name='رابط موقع الفعالية')
    arrival_time_text = models.CharField(max_length=100, blank=True, verbose_name='وقت الحضور المتوقع')
    whatsapp_group_link = models.URLField(blank=True, verbose_name='رابط مجموعة الواتساب')
    max_students = models.PositiveIntegerField(null=True, blank=True, verbose_name='الحد الأقصى للطلاب')
    is_finished = models.BooleanField(default=False, verbose_name='تم إنهاء الفعالية')

    class Meta:
        verbose_name = 'إعدادات الفعالية'
        verbose_name_plural = 'إعدادات الفعالية'

    def __str__(self):
        return self.name or 'إعدادات الفعالية'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class VIPInvite(models.Model):
    name = models.CharField(max_length=200, verbose_name='الاسم')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    title = models.CharField(max_length=255, verbose_name='الوظيفة أو الصفة')
    vip_time = models.CharField(max_length=50, verbose_name='وقت حضور الضيف', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ إرسال الدعوة')

    class Meta:
        verbose_name = 'دعوة VIP'
        verbose_name_plural = 'دعوات VIP'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class VolunteerNote(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='volunteer_notes',
        verbose_name='المستخدم',
    )
    text = models.TextField(verbose_name='نص الملاحظة')


class FailedEmail(models.Model):
    recipient = models.CharField(max_length=500, verbose_name='المستلمون')
    subject = models.CharField(max_length=255, verbose_name='العنوان')
    body_text = models.TextField(verbose_name='نص الرسالة (Text)', blank=True)
    body_html = models.TextField(verbose_name='نص الرسالة (HTML)', blank=True)
    error_message = models.TextField(verbose_name='خطأ الإرسال', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الفشل')
    retry_count = models.PositiveIntegerField(default=0, verbose_name='عدد المحاولات')

    class Meta:
        verbose_name = 'بريد بانتظار الإرسال'
        verbose_name_plural = 'الإيميلات بانتظار الإرسال'
        ordering = ['-created_at']

    def __str__(self):
        return f"إلى: {self.recipient} - {self.subject}"
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')

    class Meta:
        verbose_name = 'ملاحظة متطوع'
        verbose_name_plural = 'ملاحظات المتطوعين'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.author} - {self.created_at:%Y-%m-%d %H:%M}'


class StudentViolation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'في انتظار مراجعة الإدارة'
        RESOLVED = 'resolved', 'تمت المعالجة'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='violations',
        verbose_name='الطالب',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_violations',
        verbose_name='تم الإبلاغ بواسطة',
    )
    reason = models.TextField(verbose_name='سبب المخالفة أو الوصف')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='حالة المخالفة',
    )
    admin_action = models.CharField(max_length=255, blank=True, verbose_name='إجراء الإدارة')
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_violations',
        verbose_name='تمت المعالجة بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإبلاغ')
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ المعالجة')

    class Meta:
        verbose_name = 'مخالفة طالب'
        verbose_name_plural = 'مخالفات الطلاب'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} - {self.get_status_display()}'
