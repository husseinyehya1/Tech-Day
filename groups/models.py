from django.db import models


class Group(models.Model):
    class Level(models.TextChoices):
        PRIMARY = 'primary', 'ابتدائي'
        PREP_SEC = 'prep_sec', 'إعدادي وثانوي'

    event = models.ForeignKey(
        'dashboard.Event',
        on_delete=models.CASCADE,
        related_name='groups',
        verbose_name='الفعالية',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=50, verbose_name='اسم المجموعة')
    code = models.CharField(max_length=1, verbose_name='الكود')
    color = models.CharField(max_length=20, verbose_name='لون المجموعة')
    max_students = models.PositiveIntegerField(default=25, verbose_name='الحد الأقصى للطلاب')
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.PRIMARY,
        verbose_name='المرحلة الدراسية',
    )
    points = models.PositiveIntegerField(default=0, verbose_name='النقاط')

    class Meta:
        verbose_name = 'مجموعة'
        verbose_name_plural = 'المجموعات'
        unique_together = ('event', 'code')

    def __str__(self):
        return f'مجموعة {self.code} - {self.event.location_name if self.event else ""}'

    @property
    def student_count(self):
        return self.students.count()
