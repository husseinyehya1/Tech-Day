from django.conf import settings
from django.db import models

from groups.models import Group


class Workshop(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'قادمة'),
        ('active', 'نشطة'),
        ('finished', 'منتهية'),
    ]

    event = models.ForeignKey(
        'dashboard.Event',
        on_delete=models.CASCADE,
        related_name='workshops',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
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
    points_per_session = models.PositiveIntegerField(default=10, verbose_name='النقاط لكل جلسة')

    class Meta:
        verbose_name = 'ورشة'
        verbose_name_plural = 'الورش'

    def __str__(self):
        return self.title


class WorkshopSession(models.Model):
    PERIOD_CHOICES = [
        ('8:30-8:45', '8:30 – 8:45 (تسجيل الدخول وتنظيم المجموعات)'),
        ('8:45-9:30', '8:45 – 9:30 (الجلسة الأولى)'),
        ('9:30-9:35', '9:30 – 9:35 (فترة راحة وانتقال)'),
        ('9:35-10:20', '9:35 – 10:20 (الجلسة الثانية)'),
        ('10:20-10:25', '10:20 – 10:25 (فترة راحة وانتقال)'),
        ('10:25-11:10', '10:25 – 11:10 (الجلسة الثالثة)'),
        ('11:10-11:55', '11:10 – 11:55 (فترة الألعاب والنشاط الترفيهي)'),
        ('11:55-12:40', '11:55 – 12:40 (الجلسة الرابعة)'),
        ('12:40-12:45', '12:40 – 12:45 (فترة راحة وانتقال)'),
        ('12:45-1:30', '12:45 – 1:30 (الجلسة الخامسة)'),
        ('1:30-2:00', '1:30 – 2:00 (الختام)'),
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
        max_length=20,
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


class WorkshopFeedback(models.Model):
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name='الطالب',
    )
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name='الورشة',
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], verbose_name='التقييم'
    )
    comment = models.TextField(blank=True, verbose_name='التعليق')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')

    class Meta:
        verbose_name = 'تقييم ورشة'
        verbose_name_plural = 'تقييمات الورش'
        unique_together = ('student', 'workshop')

    def __str__(self):
        return f'{self.student} - {self.workshop} - {self.rating}'


class WorkshopResource(models.Model):
    RESOURCE_TYPES = [
        ('link', 'رابط خارجي'),
        ('code', 'كود برمجي'),
        ('presentation', 'ملف عرض'),
        ('video', 'فيديو تعليمي'),
        ('other', 'أخرى'),
    ]

    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name='resources',
        verbose_name='الورشة',
    )
    title = models.CharField(max_length=150, verbose_name='عنوان المصدر')
    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPES,
        default='link',
        verbose_name='نوع المصدر',
    )
    url = models.URLField(blank=True, null=True, verbose_name='رابط المصدر')
    file = models.FileField(upload_to='workshop_resources/', blank=True, null=True, verbose_name='ملف المصدر')
    description = models.TextField(blank=True, verbose_name='وصف قصير')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')

    class Meta:
        verbose_name = 'مصدر تعليمي'
        verbose_name_plural = 'المصادر التعليمية'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.workshop.title})'
