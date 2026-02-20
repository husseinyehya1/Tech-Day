from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=50, verbose_name='اسم المجموعة')
    code = models.CharField(max_length=1, unique=True, verbose_name='الكود')
    color = models.CharField(max_length=20, verbose_name='لون المجموعة')
    max_students = models.PositiveIntegerField(default=25, verbose_name='الحد الأقصى للطلاب')

    class Meta:
        verbose_name = 'مجموعة'
        verbose_name_plural = 'المجموعات'

    def __str__(self):
        return f'مجموعة {self.code}'

    @property
    def student_count(self):
        return self.students.count()
