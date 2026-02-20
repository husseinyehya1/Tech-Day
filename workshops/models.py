from django.conf import settings
from django.db import models

from groups.models import Group


class Workshop(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'قادمة'),
        ('active', 'نشطة'),
        ('finished', 'منتهية'),
    ]

    title = models.CharField(max_length=150, verbose_name='اسم الورشة')
    room = models.CharField(max_length=50, verbose_name='القاعة')
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_workshops',
        verbose_name='المشرف',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='upcoming',
        verbose_name='حالة الورشة',
    )

    class Meta:
        verbose_name = 'ورشة'
        verbose_name_plural = 'الورش'

    def __str__(self):
        return self.title


class WorkshopSession(models.Model):
    PERIOD_CHOICES = [
        ('9-10', '9:00 – 10:00'),
        ('10-11', '10:00 – 11:00'),
        ('11-12', '11:00 – 12:00'),
        ('12-1', '12:00 – 1:00'),
        ('1-2', '1:00 – 2:00'),
    ]

    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='الورشة',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='المجموعة',
    )
    period = models.CharField(
        max_length=10,
        choices=PERIOD_CHOICES,
        verbose_name='الفترة الزمنية',
    )
    start_time = models.TimeField(verbose_name='وقت البداية')
    end_time = models.TimeField(verbose_name='وقت النهاية')

    class Meta:
        verbose_name = 'جلسة ورشة'
        verbose_name_plural = 'جلسات الورش'
        unique_together = ('group', 'period')

    def __str__(self):
        return f'{self.workshop} - {self.group} - {self.get_period_display()}'
