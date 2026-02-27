from django.db import models

from students.models import Student
from workshops.models import WorkshopSession


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'حاضر'
        LATE = 'late', 'متأخر'
        ABSENT = 'absent', 'غائب'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name='الطالب',
    )
    session = models.ForeignKey(
        WorkshopSession,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name='جلسة الورشة',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
        verbose_name='الحالة',
    )
    scanned_at = models.DateTimeField(verbose_name='وقت التسجيل')

    class Meta:
        verbose_name = 'حضور'
        verbose_name_plural = 'سجلات الحضور'
        unique_together = ('student', 'session')

    def __str__(self):
        return f'{self.student} - {self.session} - {self.get_status_display()}'
