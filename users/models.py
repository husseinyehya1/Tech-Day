from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'مدير النظام'
        SUPERVISOR = 'supervisor', 'مشرف الورشة'
        STUDENT = 'student', 'طالب'

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.STUDENT,
        verbose_name='الدور',
    )

    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser

    def is_supervisor(self):
        return self.role == self.Roles.SUPERVISOR

    def is_student(self):
        return self.role == self.Roles.STUDENT
