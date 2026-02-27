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


class StudentRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'في انتظار المراجعة'
        APPROVED = 'approved', 'تمت الموافقة'
        REJECTED = 'rejected', 'مرفوض'

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
    student = models.OneToOneField(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registration',
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ إنشاء الطلب')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')

    class Meta:
        verbose_name = 'طلب تسجيل طالب'
        verbose_name_plural = 'طلبات تسجيل الطلاب'
        ordering = ['-created_at']

    def __str__(self):
        return self.full_name_ar
