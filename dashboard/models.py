from django.db import models


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
