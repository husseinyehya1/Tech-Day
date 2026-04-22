import hashlib
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PublicForm, PublicFormField, PublicFormSubmission, PublicFormAnswer


@override_settings(FILE_UPLOAD_MAX_MEMORY_SIZE=50 * 1024 * 1024)
class PublicFormUploadIntegrityTests(TestCase):
    def setUp(self):
        super().setUp()
        self.temp_media = tempfile.mkdtemp(prefix='test_media_')
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media, FILE_UPLOAD_TEMP_DIR=self.temp_media)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)
        super().tearDown()

    def _create_form(self):
        form = PublicForm.objects.create(
            title='Test Upload Form',
            token='upload-integrity-token',
            is_active=True,
        )
        PublicFormField.objects.create(
            form=form,
            key='full_name',
            label='الاسم',
            field_type=PublicFormField.FieldType.SHORT_TEXT,
            required=True,
            order=1,
        )
        return form

    def _get_submit_token(self, token):
        response = self.client.get(reverse('public_screen:public_form', args=[token]))
        self.assertEqual(response.status_code, 200)
        return response.context['submit_token']

    def test_profile_photo_upload_keeps_file_bytes(self):
        form = self._create_form()
        PublicFormField.objects.create(
            form=form,
            key='profile_photo',
            label='صورة شخصية',
            field_type=PublicFormField.FieldType.FILE,
            required=True,
            order=2,
        )

        original_bytes = b'\xff\xd8\xff\xe0' + os.urandom(4096)
        original_hash = hashlib.sha256(original_bytes).hexdigest()
        uploaded = SimpleUploadedFile('profile.jpg', original_bytes, content_type='image/jpeg')

        submit_token = self._get_submit_token(form.token)
        response = self.client.post(
            reverse('public_screen:public_form', args=[form.token]),
            data={
                '_submit_token': submit_token,
                'full_name': 'Ahmed Mohamed',
                'profile_photo': uploaded,
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PublicFormSubmission.objects.filter(form=form).count(), 1)
        answer = PublicFormAnswer.objects.filter(submission__form=form, field__key='profile_photo').first()
        self.assertIsNotNone(answer)
        with answer.value_file.open('rb') as f:
            stored_bytes = f.read()
        stored_hash = hashlib.sha256(stored_bytes).hexdigest()
        self.assertEqual(stored_hash, original_hash)

    def test_id_photo_two_files_keep_integrity(self):
        form = self._create_form()
        PublicFormField.objects.create(
            form=form,
            key='id_photo',
            label='صورة البطاقة',
            field_type=PublicFormField.FieldType.FILE,
            required=True,
            order=2,
        )

        first_bytes = b'\x25PDF-' + os.urandom(3072)
        second_bytes = b'\xff\xd8\xff\xe1' + os.urandom(3072)
        first_hash = hashlib.sha256(first_bytes).hexdigest()
        second_hash = hashlib.sha256(second_bytes).hexdigest()

        file1 = SimpleUploadedFile('id1.pdf', first_bytes, content_type='application/pdf')
        file2 = SimpleUploadedFile('id2.jpg', second_bytes, content_type='image/jpeg')

        submit_token = self._get_submit_token(form.token)
        response = self.client.post(
            reverse('public_screen:public_form', args=[form.token]),
            data={
                '_submit_token': submit_token,
                'full_name': 'Hussein Yahia',
                'id_photo': [file1, file2],
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        answers = list(PublicFormAnswer.objects.filter(submission__form=form, field__key='id_photo').order_by('id'))
        self.assertEqual(len(answers), 2)

        hashes = []
        for ans in answers:
            with ans.value_file.open('rb') as f:
                hashes.append(hashlib.sha256(f.read()).hexdigest())
        self.assertCountEqual(hashes, [first_hash, second_hash])
