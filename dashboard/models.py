from django.conf import settings
from django.db import models

from students.models import Student


class AdminLog(models.Model):
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='admin_logs',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
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

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
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
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name='المستخدم المستهدف'
    )
    related_support_request = models.ForeignKey(
        'StudentSupportRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='طلب الدعم المرتبط'
    )
    is_active = models.BooleanField(default=True, verbose_name='مفعّل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')

    class Meta:
        verbose_name = 'تنبيه'
        verbose_name_plural = 'التنبيهات'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Event(models.Model):
    name = models.CharField(max_length=150, default='Tech Day', verbose_name='اسم الفعالية')
    year = models.PositiveIntegerField(verbose_name='السنة', default=2026)
    location_name = models.CharField(max_length=255, blank=True, verbose_name='مكان الفعالية')
    execution_number = models.PositiveIntegerField(default=1, verbose_name='رقم التنفيذ')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='رابط الأرشفة', blank=True)
    
    start_datetime = models.DateTimeField(null=True, blank=True, verbose_name='موعد بدء الفعالية')
    location_link = models.URLField(blank=True, verbose_name='رابط موقع الفعالية')
    arrival_time_text = models.CharField(max_length=100, blank=True, verbose_name='وقت الحضور المتوقع')
    whatsapp_group_link = models.URLField(blank=True, verbose_name='رابط مجموعة الواتساب')
    event_instructions = models.TextField(blank=True, verbose_name='تعليمات الفعالية')
    max_students = models.PositiveIntegerField(null=True, blank=True, verbose_name='الحد الأقصى للطلاب')
    
    is_active = models.BooleanField(default=True, verbose_name='نشطة حالياً')
    is_archived = models.BooleanField(default=False, verbose_name='مؤرشفة')
    is_registration_closed = models.BooleanField(default=False, verbose_name='إغلاق التسجيل يدوياً')
    allow_existing_students_registration = models.BooleanField(default=True, verbose_name='السماح للطلاب المسجلين سابقاً بالتسجيل')
    is_education_admin_locked = models.BooleanField(default=False, verbose_name='قفل الإدارة التعليمية للتسجيل')
    locked_education_admin = models.CharField(max_length=150, blank=True, default='العبور', verbose_name='الإدارة التعليمية المسموح بها')
    allow_group_points = models.BooleanField(default=True, verbose_name='السماح بإضافة نقاط للمجموعات')
    is_finished = models.BooleanField(default=False, verbose_name='تم إنهاء الفعالية')
    is_maintenance_mode = models.BooleanField(default=False, verbose_name='وضع الصيانة')
    maintenance_facebook_url = models.URLField(default='https://facebook.com/edutechegypt', verbose_name='لينك الفيسبوك في الصيانة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'فعالية'
        verbose_name_plural = 'الفعاليات'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.location_name} ({self.year}/{self.execution_number})"

    def save(self, *args, **kwargs):
        if not self.slug:
            # Generate slug: {year}-{location_name}-{execution_number}
            # Handle Arabic characters using a simpler approach if slugify returns empty
            from django.utils.text import slugify
            loc_slug = slugify(self.location_name)
            if not loc_slug:
                # Fallback for Arabic/Non-ASCII characters
                loc_slug = self.location_name.replace(' ', '-')
            
            self.slug = f"{self.year}-{loc_slug}-{self.execution_number}"
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        # محاولة جلب أول فعالية نشطة
        event = cls.objects.filter(is_active=True).first()
        
        # إذا لم توجد فعالية نشطة، نبحث عن أي فعالية موجودة
        if not event:
            event = cls.objects.first()
            
        # إذا لم توجد أي فعالية على الإطلاق، ننشئ واحدة افتراضية
        if not event:
            try:
                # محاولة الإنشاء مع التعامل مع احتمالية وجود Slug مكرر
                event = cls.objects.create(
                    name="Tech Day", 
                    location_name="Main", 
                    year=2026, 
                    is_active=True
                )
            except Exception:
                # في حالة الفشل التام (مثلاً بسبب Slug)، نحاول جلب أي سجل موجود مرة أخرى
                event = cls.objects.first()
                
        return event


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
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإضافة')

    class Meta:
        verbose_name = 'ملاحظة متطوع'
        verbose_name_plural = 'ملاحظات المتطوعين'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.author.username}: {self.text[:30]}'


class SOSRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'قيد الانتظار'
        SOLVED = 'solved', 'تم الحل'

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='sos_requests',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sos_requests',
        verbose_name='المشرف',
    )
    workshop = models.ForeignKey(
        'workshops.Workshop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='الورشة/القاعة',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='الطالب المعني',
    )
    location_manual = models.CharField(max_length=255, blank=True, verbose_name='المكان (يدوي)')
    message = models.TextField(verbose_name='نص الاستغاثة')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='الحالة',
    )
    is_seen = models.BooleanField(default=False, verbose_name='تمت رؤيته')
    admin_reply = models.TextField(blank=True, verbose_name='رد الإدارة')
    reply_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت الرد')
    is_reply_seen = models.BooleanField(default=False, verbose_name='تم رؤية الرد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الطلب')

    class Meta:
        verbose_name = 'طلب استغاثة (SOS)'
        verbose_name_plural = 'طلبات الاستغاثة (SOS)'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.supervisor.get_full_name() or self.supervisor.username} - {self.get_status_display()}'


class BroadcastMessage(models.Model):
    class Target(models.TextChoices):
        ALL = 'all', 'الكل'
        STUDENTS = 'students', 'الطلاب فقط'
        SUPERVISORS = 'supervisors', 'المشرفين فقط'
        VOLUNTEERS = 'volunteers', 'المتطوعين فقط'

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='broadcast_messages',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='broadcasts',
        verbose_name='المرسل',
    )
    message = models.TextField(verbose_name='نص الإذاعة')
    target = models.CharField(
        max_length=20,
        choices=Target.choices,
        default=Target.ALL,
        verbose_name='الفئة المستهدفة',
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط حالياً')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء')

    class Meta:
        verbose_name = 'إذاعة داخلية (Broadcast)'
        verbose_name_plural = 'الإذاعات الداخلية (Broadcasts)'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_target_display()}: {self.message[:30]}'


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


class StudentViolation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'في انتظار مراجعة الإدارة'
        RESOLVED = 'resolved', 'تمت المعالجة'

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='violations',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
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


class StudentSupportRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'قيد الانتظار'
        IN_PROGRESS = 'in_progress', 'قيد المعالجة'
        SOLVED = 'solved', 'تم الحل'
        CLOSED = 'closed', 'مغلق'

    class Category(models.TextChoices):
        ATTENDANCE = 'attendance', 'مشكلة في الحضور'
        CERTIFICATE = 'certificate', 'مشكلة في الشهادة'
        ACCOUNT = 'account', 'مشكلة في الحساب'
        WORKSHOP = 'workshop', 'مشكلة في الورشة'
        OTHER = 'other', 'أخرى'

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='support_requests',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='support_requests',
        verbose_name='الطالب',
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name='فئة المشكلة',
    )
    subject = models.CharField(max_length=200, verbose_name='عنوان المشكلة')
    message = models.TextField(verbose_name='تفاصيل المشكلة')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='الحالة',
    )
    admin_reply = models.TextField(blank=True, verbose_name='رد الإدارة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الطلب')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        verbose_name = 'طلب دعم طالب'
        verbose_name_plural = 'طلبات دعم الطلاب'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.name} - {self.get_category_display()} - {self.get_status_display()}'


class AppVersion(models.Model):
    platform = models.CharField(
        max_length=20,
        choices=[('android', 'Android'), ('ios', 'iOS')],
        default='android',
        verbose_name='نظام التشغيل'
    )
    version_code = models.CharField(max_length=50, verbose_name='رقم الإصدار (e.g. 1.0.0)')
    build_number = models.IntegerField(verbose_name='رقم البناء (Build Number)')
    min_build_number = models.IntegerField(verbose_name='أقل رقم بناء مسموح به')
    download_url = models.URLField(verbose_name='رابط تحميل التحديث', blank=True)
    apk_file = models.FileField(upload_to='app_releases/', blank=True, null=True, verbose_name='ملف APK')
    release_notes = models.TextField(verbose_name='ملاحظات الإصدار', blank=True)
    is_force_update = models.BooleanField(default=False, verbose_name='تحديث إجباري')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإصدار')

    class Meta:
        verbose_name = 'إصدار التطبيق'
        verbose_name_plural = 'إصدارات التطبيق'
        ordering = ['-build_number']
        unique_together = ['platform', 'build_number']

    def __str__(self):
        return f"{self.platform.upper()} - Version {self.version_code} ({self.build_number})"
