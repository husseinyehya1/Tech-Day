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
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    checked_in = models.BooleanField(default=False, verbose_name='تم تسجيل دخول الفعالية')
    checked_in_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت تسجيل الدخول للفعالية')
    is_blacklisted = models.BooleanField(default=False, verbose_name='في القائمة السوداء')
    grade = models.CharField(max_length=50, blank=True, verbose_name='السنة الدراسية')
    is_certificate_banned = models.BooleanField(default=False, verbose_name='محروم من الشهادة')
    points = models.PositiveIntegerField(default=0, verbose_name='النقاط')
    
    # حقول إرسال الشهادة للبريد
    cert_emails_sent = models.PositiveIntegerField(default=0, verbose_name='عدد مرات إرسال الشهادة')
    last_cert_email_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ آخر إرسال للشهادة')

    class Meta:
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'

    def __str__(self):
        return f'{self.name} ({self.student_id})'

    def is_registered_for_event(self, event):
        return self.registrations.filter(
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()

    @property
    def is_registered_for_current_event(self):
        from dashboard.models import Event
        event = Event.get_current()
        if not event:
            return False
        return self.is_registered_for_event(event)


class StudentRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'في انتظار المراجعة'
        APPROVED = 'approved', 'تمت الموافقة'
        REJECTED = 'rejected', 'مرفوض'

    event = models.ForeignKey(
        'dashboard.Event',
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    full_name_ar = models.CharField(max_length=200, verbose_name='الاسم الكامل (عربي)')
    full_name_en = models.CharField(max_length=200, verbose_name='الاسم الكامل (إنجليزي)')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    school = models.CharField(max_length=150, verbose_name='المدرسة')
    education_admin = models.CharField(max_length=150, verbose_name='الإدارة التعليمية')
    grade = models.CharField(max_length=50, blank=True, verbose_name='السنة الدراسية')
    interests = models.TextField(blank=True, verbose_name='الاهتمامات والهوايات')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='حالة الطلب',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registrations',
        verbose_name='الطالب المرتبط',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_registrations',
        verbose_name='تمت الموافقة بواسطة',
    )
    removed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإزالة من الفعالية')
    removed_reason = models.TextField(blank=True, verbose_name='سبب الإزالة من الفعالية')
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='removed_registrations',
        verbose_name='تمت الإزالة بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ إنشاء الطلب')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')

    class Meta:
        verbose_name = 'طلب تسجيل طالب'
        verbose_name_plural = 'طلبات تسجيل الطلاب'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'status', 'removed_at']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]

    def __str__(self):
        return self.full_name_ar


class Badge(models.Model):
    class CriteriaType(models.TextChoices):
        POINTS = 'points', 'نقاط محددة'
        ATTENDANCE_RATE = 'attendance_rate', 'نسبة حضور'
        MANUAL = 'manual', 'يدوي (بواسطة الأدمن)'

    event = models.ForeignKey(
        'dashboard.Event',
        on_delete=models.CASCADE,
        related_name='badges',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100, verbose_name='اسم الوسام')
    description = models.TextField(verbose_name='وصف الوسام')
    icon = models.CharField(max_length=50, default='award', verbose_name='أيقونة الوسام (Lucide)')
    color = models.CharField(max_length=20, default='#3b82f6', verbose_name='لون الوسام')
    criteria_type = models.CharField(
        max_length=20,
        choices=CriteriaType.choices,
        default=CriteriaType.MANUAL,
        verbose_name='نوع المعيار',
    )
    criteria_value = models.PositiveIntegerField(default=0, verbose_name='قيمة المعيار (النقاط أو النسبة %)')

    class Meta:
        verbose_name = 'وسام'
        verbose_name_plural = 'الأوسمة'

    def __str__(self):
        return self.name


class StudentEventStats(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='event_stats',
        verbose_name='الطالب',
    )
    event = models.ForeignKey(
        'dashboard.Event',
        on_delete=models.CASCADE,
        related_name='student_stats',
        verbose_name='الفعالية',
    )
    points = models.PositiveIntegerField(default=0, verbose_name='النقاط في هذه الفعالية')
    checked_in = models.BooleanField(default=False, verbose_name='تم تسجيل الحضور')
    checked_in_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت تسجيل الحضور')
    is_certificate_generated = models.BooleanField(default=False, verbose_name='تم إصدار الشهادة')

    class Meta:
        verbose_name = 'إحصائيات طالب في فعالية'
        verbose_name_plural = 'إحصائيات الطلاب في الفعاليات'
        unique_together = ('student', 'event')

    def __str__(self):
        return f'{self.student.name} - {self.event.location_name}'


class StudentBadge(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='badges',
        verbose_name='الطالب',
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='awarded_to',
        verbose_name='الوسام',
    )
    earned_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحصول عليه')
    is_seen_by_student = models.BooleanField(default=False, verbose_name='تمت رؤيته من قبل الطالب')

    class Meta:
        verbose_name = 'وسام طالب'
        verbose_name_plural = 'أوسمة الطلاب'
        unique_together = ('student', 'badge')

    def __str__(self):
        return f'{self.student.name} - {self.badge.name}'


class StudentWorkshopNote(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='workshop_notes',
        verbose_name='الطالب',
    )
    workshop = models.ForeignKey(
        'workshops.Workshop',
        on_delete=models.CASCADE,
        related_name='student_notes',
        verbose_name='الورشة',
    )
    content = models.TextField(verbose_name='محتوى الملاحظة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الكتابة')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        verbose_name = 'مذكرة تعلم طالب'
        verbose_name_plural = 'مذكرات تعلم الطلاب'
        unique_together = ('student', 'workshop')

    def __str__(self):
        return f'مذكرة {self.student.name} لورشة {self.workshop.title}'
