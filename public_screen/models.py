import uuid

from django.conf import settings
from django.db import models


class PublicForm(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    token = models.CharField(max_length=128, unique=True)
    custom_slug = models.SlugField(max_length=120, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_public_forms',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PublicFormField(models.Model):
    class FieldType(models.TextChoices):
        SHORT_TEXT = 'short_text', 'إجابة قصيرة'
        PARAGRAPH = 'paragraph', 'فقرة'
        DROPDOWN = 'dropdown', 'قائمة منسدلة'
        RADIO = 'radio', 'اختيار من متعدد'
        CHECKBOXES = 'checkboxes', 'مربعات اختيار'
        FILE = 'file', 'رفع ملف'
        AGREEMENT = 'agreement', 'مربع إقرار'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(PublicForm, on_delete=models.CASCADE, related_name='fields')
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=255)
    help_text = models.TextField(blank=True, default='')
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    choices = models.JSONField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('form', 'key')
        ordering = ['order', 'label']

    def __str__(self):
        return f'{self.form_id}:{self.key}'


class PublicFormSubmission(models.Model):
    form = models.ForeignKey(PublicForm, on_delete=models.CASCADE, related_name='submissions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.form_id}:{self.id}'


class PublicFormAnswer(models.Model):
    submission = models.ForeignKey(PublicFormSubmission, on_delete=models.CASCADE, related_name='answers')
    field = models.ForeignKey(PublicFormField, on_delete=models.CASCADE, related_name='answers')
    value_text = models.TextField(blank=True, default='')
    value_file = models.FileField(upload_to='public-forms/uploads/', blank=True, null=True)

    def __str__(self):
        return f'{self.submission_id}:{self.field_id}'
