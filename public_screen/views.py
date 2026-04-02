from django.conf import settings
from django.contrib import messages
from django import forms
from django.db import transaction
from django.db.models import Count, Q, Avg
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import get_user_model
import os
import uuid
from datetime import date
import logging
from django.core.files.storage import default_storage

from techday.utils import send_email_async, get_styled_email_html, send_registration_confirmation_email

from attendance.models import Attendance
from groups.models import Group
from students.models import Student, StudentRegistration
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback
from dashboard.models import Event, AdminLog, AppVersion
from .models import PublicForm, PublicFormField, PublicFormSubmission, PublicFormAnswer


User = get_user_model()
logger = logging.getLogger(__name__)


class StyledRadioSelect(forms.RadioSelect):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        option_attrs = option.get('attrs') or {}
        existing = (option_attrs.get('class') or '').strip()
        option_attrs['class'] = (existing + ' h-4 w-4 accent-cyan-400').strip()
        option['attrs'] = option_attrs
        return option


class StyledCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        option_attrs = option.get('attrs') or {}
        existing = (option_attrs.get('class') or '').strip()
        option_attrs['class'] = (existing + ' h-4 w-4 accent-cyan-400').strip()
        option['attrs'] = option_attrs
        return option


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if not data:
            if self.required:
                raise forms.ValidationError('هذا الحقل مطلوب.')
            return []
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data if d]
        return [single_clean(data, initial)]


def _validate_uploaded_file(uploaded_file, allowed_extensions, max_mb=10):
    ext = os.path.splitext((uploaded_file.name or '').lower())[1]
    if ext not in allowed_extensions:
        raise forms.ValidationError('صيغة الملف غير مدعومة.')
    max_bytes = max_mb * 1024 * 1024
    if uploaded_file.size and uploaded_file.size > max_bytes:
        raise forms.ValidationError(f'حجم الملف كبير. الحد الأقصى {max_mb}MB.')


def _safe_file_stem(text):
    text = (text or '').strip()
    cleaned = ''.join(ch if ch.isalnum() else '_' for ch in text)
    cleaned = cleaned.strip('_')
    return (cleaned[:80] or 'submission')


def _build_target_filename(uploaded_file, person_name, file_kind, index=None):
    ext = os.path.splitext((uploaded_file.name or '').strip())[1].lower() or ''
    stem = _safe_file_stem(person_name)
    suffix = _safe_file_stem(file_kind)
    idx = f'_{index}' if index else ''
    return f'{stem}_{suffix}{idx}{ext}'


def _extract_birth_data_from_national_id(national_id):
    nid = ''.join(ch for ch in (national_id or '') if ch.isdigit())
    if len(nid) != 14:
        raise forms.ValidationError('الرقم القومي يجب أن يكون 14 رقم.')
    century_map = {'2': 1900, '3': 2000}
    if nid[0] not in century_map:
        raise forms.ValidationError('الرقم القومي غير صحيح.')
    year = century_map[nid[0]] + int(nid[1:3])
    month = int(nid[3:5])
    day = int(nid[5:7])
    try:
        birth_date = date(year, month, day)
    except ValueError:
        raise forms.ValidationError('تاريخ الميلاد داخل الرقم القومي غير صحيح.')
    gov_map = {
        '01': 'القاهرة', '02': 'الإسكندرية', '03': 'بورسعيد', '04': 'السويس',
        '11': 'دمياط', '12': 'الدقهلية', '13': 'الشرقية', '14': 'القليوبية',
        '15': 'كفر الشيخ', '16': 'الغربية', '17': 'المنوفية', '18': 'البحيرة',
        '19': 'الإسماعيلية', '21': 'الجيزة', '22': 'بني سويف', '23': 'الفيوم',
        '24': 'المنيا', '25': 'أسيوط', '26': 'سوهاج', '27': 'قنا',
        '28': 'أسوان', '29': 'الأقصر', '31': 'البحر الأحمر', '32': 'الوادي الجديد',
        '33': 'مطروح', '34': 'شمال سيناء', '35': 'جنوب سيناء', '88': 'خارج الجمهورية',
    }
    governorate = gov_map.get(nid[7:9], 'غير معروف')
    return birth_date.strftime('%Y-%m-%d'), governorate, nid


def public_screen_view(request):
    now = timezone.localtime()
    event = Event.get_current()
    if not event:
        # Create a default event if none exists
        event = Event.objects.create(name="Tech Day", location_name="Main", year=2026, is_active=True)
        
    total_registered = StudentRegistration.objects.filter(
        event=event,
        status=StudentRegistration.Status.APPROVED,
        removed_at__isnull=True,
    ).count()
    total_students = total_registered
    is_full = event.max_students is not None and total_registered >= event.max_students
    is_closed = event.is_registration_closed or event.is_finished

    if request.method == 'POST':
        if is_closed:
            messages.error(request, 'عذراً، تم إغلاق باب التسجيل في هذه الفعالية حالياً.')
            return redirect('public_screen:public_screen')
        
        if is_full:
            messages.error(request, 'عذراً، تم الوصول للحد الأقصى للمسجلين في هذه الفعالية.')
            return redirect('public_screen:public_screen')
        
        full_name_ar = (request.POST.get('full_name_ar') or '').strip()
        full_name_en = (request.POST.get('full_name_en') or '').strip()
        email = (request.POST.get('email') or '').strip()
        phone_number = (request.POST.get('phone_number') or '').strip()
        school = 'إدارة غرب شبرا التعليمية'
        education_admin = (request.POST.get('education_admin') or '').strip()
        grade = (request.POST.get('grade') or '').strip()
        interests = (request.POST.get('interests') or '').strip()
        if not full_name_ar or not full_name_en or not email or not phone_number or not school or not education_admin or not grade:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة في نموذج التسجيل.')
            return redirect('public_screen:public_screen')

        if getattr(event, 'is_education_admin_locked', False):
            locked_admin = (getattr(event, 'locked_education_admin', '') or '').strip() or 'العبور'
            if education_admin != locked_admin:
                messages.error(request, f'هذه الفعالية مخصصة لطلاب إدارة {locked_admin} فقط.')
                return redirect('public_screen:public_screen')
        
        # التحقق إذا كان الطالب مسجلاً مسبقاً في النظام (لديه حساب)
        existing_student = Student.objects.filter(Q(email__iexact=email) | Q(phone_number=phone_number)).first()
        
        if existing_student:
            if not getattr(event, 'allow_existing_students_registration', True):
                messages.error(request, 'التسجيل في هذه الفعالية متاح للطلاب الجدد فقط. في حالة وجود مشكلة تواصل مع الإدارة.')
                return redirect('public_screen:public_screen')
            # التحقق إذا كان سجل بالفعل في هذه الفعالية
            already_registered = StudentRegistration.objects.filter(
                student=existing_student,
                event=event,
                status=StudentRegistration.Status.APPROVED,
                removed_at__isnull=True,
            ).exists()
            
            if already_registered:
                messages.info(request, 'أنت مسجل بالفعل في هذه الفعالية.')
                return redirect('public_screen:public_screen')
            
            # إنشاء طلب تسجيل موافق عليه تلقائياً للطالب الحالي
            registration = StudentRegistration.objects.create(
                event=event,
                student=existing_student,
                full_name_ar=full_name_ar,
                full_name_en=full_name_en,
                email=email,
                phone_number=phone_number,
                school=school,
                education_admin=education_admin,
                grade=grade,
                interests=interests,
                status=StudentRegistration.Status.APPROVED,
                approved_at=timezone.now()
            )
            
            # إرسال تفاصيل الفعالية والـ QR مباشرة
            subject = f'تأكيد حجز مكان في فعالية {event.name} – EduTech Egypt'
            whatsapp_block_html = ""
            if event.whatsapp_group_link:
                whatsapp_block_html = f"""
                  <tr>
                    <td style="padding:12px 0 0 0;">
                      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-radius:16px;background-color:#020617;border:1px solid #25d366;">
                        <tr>
                          <td style="padding:14px 16px;text-align:center;">
                            <p style="margin:0 0 10px;font-size:13px;color:#e5e7eb;font-weight:600;">
                              💬 مجموعة الواتساب الرسمية
                            </p>
                            <a href="{event.whatsapp_group_link}"
                               style="display:inline-block;padding:10px 18px;border-radius:999px;background-color:#25d366;color:#ffffff;font-size:13px;font-weight:700;text-decoration:none;">
                              الانضمام لمجموعة الواتساب
                            </a>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                """

            content_blocks = f"""
                <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #1e293b;text-align:center;">
                  <p class="td-email-text-main" style="margin:0 0 16px;font-size:15px;color:#e5e7eb;line-height:1.6;">
                    مرحباً بعودتك! تم تأكيد حجز مكانك في فعالية <b>{event.name}</b> بنجاح.
                  </p>
                  <div class="td-email-box" style="padding:20px;border-radius:20px;background-color:#020617;border:1px solid #1e293b;margin:20px 0;text-align:center;">
                    <p style="margin:0 0 12px;font-size:14px;color:#e5e7eb;font-weight:700;">🎫 رمز الـ QR الخاص بحضورك</p>
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={existing_student.student_id}" alt="QR Code" style="display:block;margin:0 auto;border-radius:12px;border:4px solid #ffffff;">
                    <p style="margin:12px 0 0;font-size:12px;color:#94a3b8;">استخدم هذا الرمز لتسجيل حضورك عند بوابة الدخول.</p>
                  </div>
                  {whatsapp_block_html}
                </div>
            """
            
            html_body = get_styled_email_html(
                subject=subject,
                preview_text=f"تفاصيل حضورك في فعالية {event.name}",
                title="✅ تم تأكيد حجز مكانك",
                main_text=f"مرحبًا {existing_student.name}، يسعدنا انضمامك إلينا مرة أخرى.",
                content_blocks_html=content_blocks
            )
            
            from django.core.mail import EmailMultiAlternatives
            message = EmailMultiAlternatives(
                subject,
                f"مرحباً {existing_student.name}، تم تأكيد حجز مكانك في الفعالية بنجاح.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            message.attach_alternative(html_body, 'text/html')
            send_email_async(message, 'إرسال تأكيد حجز مكان لطالب مسجل مسبقاً')
            
            messages.success(request, 'تم تأكيد حجز مكانك بنجاح! تم إرسال رمز الـ QR وتفاصيل الفعالية إلى بريدك الإلكتروني.')
            return redirect('public_screen:public_screen')

        # منطق الطلاب الجدد (ينتظر الموافقة)
        existing_pending = StudentRegistration.objects.filter(
            Q(email__iexact=email) | Q(phone_number=phone_number),
            event=event,
            status=StudentRegistration.Status.PENDING,
        ).exists()
        if existing_pending:
            messages.info(request, 'طلب التسجيل لهذا البريد أو رقم الهاتف قيد المراجعة بالفعل.')
            return redirect('public_screen:public_screen')
        registration = StudentRegistration.objects.create(
            event=event,
            full_name_ar=full_name_ar,
            full_name_en=full_name_en,
            email=email,
            phone_number=phone_number,
            school=school,
            education_admin=education_admin,
            grade=grade,
            interests=interests,
        )
        subject = 'تم استلام طلب التسجيل في فعالية Tech Day – EduTech Egypt'
        text_body = (
            f'مرحبًا {registration.full_name_ar},\n\n'
            f'تم استلام طلب التسجيل الخاص بك لحضور فعالية Tech Day – الفريق التقني بالقليوبية.\n\n'
            f'سيتم مراجعة طلبك من قبل الإدارة، وسيتم إرسال بيانات حسابك على النظام في حال الموافقة.\n\n'
            f'في حال وجود أي استفسار يمكنك الرد على هذه الرسالة.\n\n'
            f'تحياتنا،\n'
            f'EduTech Egypt System'
        )
        
        content_blocks = f"""
            <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #1e293b;text-align:center;">
              <p class="td-email-text-main" style="margin:0 0 16px;font-size:15px;color:#e5e7eb;line-height:1.6;">
                تم استلام طلب تسجيلك بنجاح وجارٍ مراجعته من قبل إدارة الفعالية.
              </p>
              <p class="td-email-text-muted" style="margin:0;font-size:13px;color:#cbd5f5;">
                سوف تتلقى بريداً إلكترونياً آخر يحتوي على بيانات الدخول بمجرد الموافقة على طلبك.
              </p>
            </div>
        """
        
        html_body = get_styled_email_html(
            subject=subject,
            preview_text="بخصوص طلب تسجيلك في فعالية Tech Day",
            title="📥 تم استلام طلبك بنجاح",
            main_text=f"مرحبًا {registration.full_name_ar}، نشكرك على رغبتك في الانضمام إلينا.",
            content_blocks_html=content_blocks
        )
        
        from django.core.mail import EmailMultiAlternatives
        message = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [registration.email],
        )
        message.attach_alternative(html_body, 'text/html')
        send_email_async(message, 'استلام طلب تسجيل جديد')
        
        return redirect('public_screen:registration_success')

    # Basic context
    # الطلاب المسجلين والموافق عليهم في هذه الفعالية
    current_registrations = StudentRegistration.objects.filter(
        event=event,
        status=StudentRegistration.Status.APPROVED,
        removed_at__isnull=True,
    )
    current_students_ids = current_registrations.values_list('student_id', flat=True)
    total_students = current_registrations.count()
    
    total_present = Student.objects.filter(id__in=current_students_ids, checked_in=True).count()
    groups = Group.objects.filter(event=event)
    best_groups = groups.order_by('-points')[:5]
    
    # Advanced Stats for Finished Event
    stats_by_admin = []
    stats_by_grade = []
    top_points_students = []
    top_workshops = []
    volunteers = []
    total_feedbacks = 0
    certificates_sent = False
    if event.is_finished:
        # Stats by Admin
        stats_by_admin = Student.objects.filter(id__in=current_students_ids).values('education_admin').annotate(
            count=Count('id'),
            checked_in_count=Count('id', filter=Q(checked_in=True))
        ).order_by('-count')

        # Stats by Grade
        grade_map = {
            '4-prim': 'الرابع الابتدائي', '5-prim': 'الخامس الابتدائي', '6-prim': 'السادس الابتدائي',
            '1-prep': 'الأول الإعدادي', '2-prep': 'الثاني الإعدادي', '3-prep': 'الثالث الإعدادي',
            '1-sec': 'الأول الثانوي', '2-sec': 'الثاني الثانوي', '3-sec': 'الثالث الثانوي',
        }
        stats_by_grade_raw = Student.objects.filter(id__in=current_students_ids).values('grade').annotate(count=Count('id')).order_by('grade')
        for item in stats_by_grade_raw:
            stats_by_grade.append({
                'name': grade_map.get(item['grade'], item['grade'] or 'غير محدد'),
                'count': item['count']
            })
        
        # Top Students
        top_points_students = Student.objects.filter(id__in=current_students_ids).select_related('group').order_by('-points')[:10]

        # Top Rated Workshops
        top_workshops_raw = Workshop.objects.filter(event=event).annotate(
            avg_rating=Avg('feedbacks__rating'),
            feedback_count=Count('feedbacks')
        ).filter(feedback_count__gt=0).order_by('-avg_rating')[:3]

        for w in top_workshops_raw:
            top_workshops.append({
                'title': w.title,
                'avg_rating': round(w.avg_rating, 1) if w.avg_rating else 0,
                'rating_percent': round(w.avg_rating * 20, 1) if w.avg_rating else 0,
                'feedback_count': w.feedback_count
            })

        total_feedbacks = WorkshopFeedback.objects.filter(workshop__event=event).count()

        certificates_sent = Student.objects.filter(id__in=current_students_ids, cert_emails_sent__gt=0).exists()

        # Volunteers
        volunteers_raw = User.objects.filter(role=User.Roles.VOLUNTEER).values_list('first_name', 'last_name')
        volunteers = [f"{v[0]} {v[1]}" for v in volunteers_raw if v[0]]

    current_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(group__event=event, start_time__lte=now.time(), end_time__gte=now.time())
        .first()
    )
    next_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(group__event=event, start_time__gt=now.time())
        .order_by('start_time')
        .first()
    )

    schedule_groups = Group.objects.filter(event=event).order_by('code')
    schedule_periods = WorkshopSession.PERIOD_CHOICES
    schedule_sessions = (
        WorkshopSession.objects.select_related('workshop', 'group')
        .filter(group__event=event)
        .all()
    )

    all_education_admins = [
        'بنها', 'طوخ', 'كفر شكر', 'شبين القناطر', 'الخانكة', 'قها',
        'قليوب', 'القناطر الخيرية', 'غرب شبرا الخيمة', 'شرق شبرا الخيمة',
        'الخصوص', 'العبور',
    ]
    if getattr(event, 'is_education_admin_locked', False):
        locked_admin = (getattr(event, 'locked_education_admin', '') or '').strip() or 'العبور'
        education_admins = [locked_admin]
    else:
        education_admins = all_education_admins

    context = {
        'now': now,
        'current_session': current_session,
        'next_session': next_session,
        'total_present': total_present,
        'total_students': total_students,
        'total_students_neg': -total_students,
        'is_full': is_full,
        'is_closed': is_closed,
        'groups': groups,
        'best_groups': best_groups,
        'event': event,
        'education_admins': education_admins,
        # Finished Event Stats
        'stats_by_admin': stats_by_admin,
        'stats_by_grade': stats_by_grade,
        'top_points_students': top_points_students,
        'top_workshops': top_workshops,
        'volunteers': volunteers,
        'total_feedbacks': total_feedbacks,
        'certificates_sent': certificates_sent,
        'attendance_rate': round((total_present / total_students * 100), 1) if total_students > 0 else 0,
        'schedule_groups': schedule_groups,
        'schedule_periods': schedule_periods,
        'schedule_sessions': schedule_sessions,
    }
    return render(request, 'public_screen/public_screen.html', context)


def registration_success_view(request):
    return render(request, 'public_screen/registration_success.html')


def terms_view(request):
    return render(request, 'public_screen/terms.html')


def mobile_app_download_view(request):
    latest_android = AppVersion.objects.filter(platform='android').order_by('-build_number').first()
    latest_ios = AppVersion.objects.filter(platform='ios').order_by('-build_number').first()

    def resolve_download_url(version_obj):
        if not version_obj:
            return ''
        if version_obj.download_url:
            return version_obj.download_url
        if version_obj.apk_file:
            return request.build_absolute_uri(version_obj.apk_file.url)
        return ''

    context = {
        'latest_android': latest_android,
        'latest_android_download_url': resolve_download_url(latest_android),
        'latest_ios': latest_ios,
        'latest_ios_download_url': resolve_download_url(latest_ios),
    }
    return render(request, 'public_screen/mobile_app_download.html', context)


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR') or ''
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def public_form_view(request, token):
    form_obj = PublicForm.objects.filter(Q(token=token) | Q(custom_slug=token), is_active=True).first()
    if not form_obj:
        raise Http404()

    fields = list(form_obj.fields.all())
    form_fields = {}
    for f in fields:
        if f.field_type == PublicFormField.FieldType.SHORT_TEXT:
            attrs = {
                'class': 'w-full rounded-2xl bg-slate-950/50 border border-slate-800 px-4 py-3.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all',
            }
            if f.key == 'national_id':
                attrs.update({'inputmode': 'numeric', 'maxlength': '14', 'pattern': r'\d{14}'})
            if f.key in {'birth_date', 'birth_governorate'}:
                attrs.update({'readonly': 'readonly', 'tabindex': '-1'})
            form_fields[f.key] = forms.CharField(
                required=f.required,
                label=f.label,
                help_text=f.help_text,
                widget=forms.TextInput(
                    attrs=attrs
                ),
            )
        elif f.field_type == PublicFormField.FieldType.PARAGRAPH:
            form_fields[f.key] = forms.CharField(
                required=f.required,
                label=f.label,
                help_text=f.help_text,
                widget=forms.Textarea(
                    attrs={
                        'rows': 4,
                        'class': 'w-full rounded-2xl bg-slate-950/50 border border-slate-800 px-4 py-3.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all resize-none',
                    }
                ),
            )
        elif f.field_type == PublicFormField.FieldType.DROPDOWN:
            choices = [(c, c) for c in (f.choices or [])]
            form_fields[f.key] = forms.ChoiceField(
                required=f.required,
                label=f.label,
                help_text=f.help_text,
                choices=[('', 'اختر')] + choices,
                widget=forms.Select(
                    attrs={
                        'class': 'w-full rounded-2xl bg-slate-950/50 border border-slate-800 px-4 py-3.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all',
                    }
                ),
            )
        elif f.field_type == PublicFormField.FieldType.RADIO:
            choices = [(c, c) for c in (f.choices or [])]
            form_fields[f.key] = forms.ChoiceField(
                required=f.required,
                label=f.label,
                help_text=f.help_text,
                choices=choices,
                widget=StyledRadioSelect,
            )
        elif f.field_type == PublicFormField.FieldType.CHECKBOXES:
            choices = [(c, c) for c in (f.choices or [])]
            form_fields[f.key] = forms.MultipleChoiceField(
                required=f.required,
                label=f.label,
                help_text=f.help_text,
                choices=choices,
                widget=StyledCheckboxSelectMultiple,
            )
        elif f.field_type == PublicFormField.FieldType.FILE:
            if f.key == 'id_photo':
                form_fields[f.key] = MultiFileField(
                    required=f.required,
                    label=f.label,
                    help_text=f.help_text,
                    widget=MultiFileInput(
                        attrs={
                            'class': 'w-full rounded-2xl bg-slate-950/50 border border-slate-800 px-4 py-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all',
                            'accept': '.jpg,.jpeg,.png,.webp,.heic,.heif,.pdf',
                        }
                    ),
                )
            else:
                accept_value = '.jpg,.jpeg,.png,.webp,.heic,.heif'
                if f.key != 'profile_photo':
                    accept_value = '.jpg,.jpeg,.png,.webp,.heic,.heif,.pdf'
                form_fields[f.key] = forms.FileField(
                    required=f.required,
                    label=f.label,
                    help_text=f.help_text,
                    widget=forms.ClearableFileInput(
                        attrs={
                            'class': 'w-full rounded-2xl bg-slate-950/50 border border-slate-800 px-4 py-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all',
                            'accept': accept_value,
                        }
                    ),
                )
        elif f.field_type == PublicFormField.FieldType.AGREEMENT:
            form_fields[f.key] = forms.BooleanField(
                required=True,
                label=f.label,
                help_text=f.help_text,
                widget=forms.CheckboxInput(attrs={'class': 'mt-1 h-4 w-4 accent-cyan-400'}),
            )

    DynamicForm = type('DynamicForm', (forms.Form,), form_fields)
    session_key = 'public_form_submit_tokens'

    def issue_submit_token():
        submit_token = uuid.uuid4().hex
        token_map = request.session.get(session_key) or {}
        token_map[submit_token] = {'form_id': form_obj.id}
        if len(token_map) > 30:
            keys = list(token_map.keys())[-30:]
            token_map = {k: token_map[k] for k in keys}
        request.session[session_key] = token_map
        request.session.modified = True
        return submit_token

    if request.method == 'POST':
        form = DynamicForm(request.POST, request.FILES)
        if form.is_valid():
            national_id_field_exists = any(f.key == 'national_id' for f in fields)
            birth_date_field_exists = any(f.key == 'birth_date' for f in fields)
            birth_governorate_field_exists = any(f.key == 'birth_governorate' for f in fields)
            if national_id_field_exists:
                try:
                    birth_date_value, birth_governorate_value, normalized_nid = _extract_birth_data_from_national_id(
                        form.cleaned_data.get('national_id')
                    )
                except forms.ValidationError as ex:
                    form.add_error('national_id', ex.messages[0])
                    render_fields = [{'def': f, 'field': form[f.key]} for f in fields if f.key in form.fields]
                    has_profile_photo = any(f.key == 'profile_photo' for f in fields)
                    submit_token = issue_submit_token()
                    return render(
                        request,
                        'public_screen/public_form.html',
                        {
                            'form_obj': form_obj,
                            'form': form,
                            'render_fields': render_fields,
                            'has_profile_photo': has_profile_photo,
                            'submit_token': submit_token,
                        },
                    )
                form.cleaned_data['national_id'] = normalized_nid
                if birth_date_field_exists:
                    form.cleaned_data['birth_date'] = birth_date_value
                if birth_governorate_field_exists:
                    form.cleaned_data['birth_governorate'] = birth_governorate_value

            submit_token = (request.POST.get('_submit_token') or '').strip()
            token_map = request.session.get(session_key) or {}
            payload = token_map.get(submit_token)
            public_key = form_obj.custom_slug or form_obj.token
            if not submit_token or not payload or payload.get('form_id') != form_obj.id:
                return redirect('public_screen:public_form_success', token=public_key)
            token_map.pop(submit_token, None)
            request.session[session_key] = token_map
            request.session.modified = True

            image_only_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
            image_or_pdf_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.pdf'}

            validated_file_payload = {}
            for f in fields:
                if f.field_type != PublicFormField.FieldType.FILE:
                    continue
                if f.key == 'id_photo':
                    files = request.FILES.getlist(f.key)
                    if len(files) > 2:
                        form.add_error(f.key, 'يمكن رفع ملفين كحد أقصى لهذا الحقل.')
                        continue
                    clean_files = []
                    for uploaded in files:
                        try:
                            _validate_uploaded_file(uploaded, image_or_pdf_exts, max_mb=10)
                        except forms.ValidationError as ex:
                            form.add_error(f.key, f'{uploaded.name}: {ex.messages[0]}')
                            continue
                        clean_files.append(uploaded)
                    validated_file_payload[f.key] = clean_files
                else:
                    uploaded = request.FILES.get(f.key)
                    if not uploaded:
                        validated_file_payload[f.key] = None
                        continue
                    try:
                        if f.key == 'profile_photo':
                            _validate_uploaded_file(uploaded, image_only_exts, max_mb=10)
                        else:
                            _validate_uploaded_file(uploaded, image_or_pdf_exts, max_mb=10)
                    except forms.ValidationError as ex:
                        form.add_error(f.key, ex.messages[0])
                        continue
                    validated_file_payload[f.key] = uploaded

            if form.errors:
                render_fields = [{'def': f, 'field': form[f.key]} for f in fields if f.key in form.fields]
                has_profile_photo = any(f.key == 'profile_photo' for f in fields)
                submit_token = issue_submit_token()
                return render(
                    request,
                    'public_screen/public_form.html',
                    {
                        'form_obj': form_obj,
                        'form': form,
                        'render_fields': render_fields,
                        'has_profile_photo': has_profile_photo,
                        'submit_token': submit_token,
                    },
                )

            saved_file_names = []
            try:
                with transaction.atomic():
                    submission = PublicFormSubmission.objects.create(
                        form=form_obj,
                        ip_address=_get_client_ip(request),
                        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:5000],
                    )
                    full_name_for_files = form.cleaned_data.get('full_name') or form.cleaned_data.get('full_name_ar') or 'submission'
                    file_label_map = {
                        'profile_photo': 'personal_photo',
                        'birth_certificate_photo': 'birth_certificate',
                        'id_photo': 'id_card',
                    }
                    answers = []
                    for f in fields:
                        val = form.cleaned_data.get(f.key)
                        if f.field_type == PublicFormField.FieldType.FILE:
                            if f.key == 'id_photo':
                                for idx, file_obj in enumerate(validated_file_payload.get(f.key, []), start=1):
                                    file_name = _build_target_filename(
                                        file_obj,
                                        full_name_for_files,
                                        file_label_map.get(f.key, f.key),
                                        idx,
                                    )
                                    answer = PublicFormAnswer(
                                        submission=submission,
                                        field=f,
                                    )
                                    answer.value_file.save(file_name, file_obj, save=False)
                                    answer.save()
                                    if answer.value_file and answer.value_file.name:
                                        saved_file_names.append(answer.value_file.name)
                            else:
                                file_obj = validated_file_payload.get(f.key)
                                if file_obj:
                                    file_name = _build_target_filename(
                                        file_obj,
                                        full_name_for_files,
                                        file_label_map.get(f.key, f.key),
                                    )
                                    answer = PublicFormAnswer(
                                        submission=submission,
                                        field=f,
                                    )
                                    answer.value_file.save(file_name, file_obj, save=False)
                                    answer.save()
                                    if answer.value_file and answer.value_file.name:
                                        saved_file_names.append(answer.value_file.name)
                        elif f.field_type == PublicFormField.FieldType.CHECKBOXES:
                            answers.append(
                                PublicFormAnswer(
                                    submission=submission,
                                    field=f,
                                    value_text='\n'.join(val or []),
                                )
                            )
                        elif f.field_type == PublicFormField.FieldType.AGREEMENT:
                            answers.append(
                                PublicFormAnswer(
                                    submission=submission,
                                    field=f,
                                    value_text='true' if val else 'false',
                                )
                            )
                        else:
                            answers.append(
                                PublicFormAnswer(
                                    submission=submission,
                                    field=f,
                                    value_text=str(val or ''),
                                )
                            )
                    if answers:
                        PublicFormAnswer.objects.bulk_create(answers)
            except Exception:
                for file_name in saved_file_names:
                    try:
                        if default_storage.exists(file_name):
                            default_storage.delete(file_name)
                    except Exception:
                        pass
                logger.exception('Public form submission failed for form_id=%s', form_obj.id)
                return redirect('public_screen:public_form_failed', token=public_key)

            return redirect('public_screen:public_form_success', token=public_key)
    else:
        form = DynamicForm()

    render_fields = [{'def': f, 'field': form[f.key]} for f in fields if f.key in form.fields]
    has_profile_photo = any(f.key == 'profile_photo' for f in fields)
    submit_token = issue_submit_token()

    return render(
        request,
        'public_screen/public_form.html',
        {
            'form_obj': form_obj,
            'form': form,
            'render_fields': render_fields,
            'has_profile_photo': has_profile_photo,
            'submit_token': submit_token,
        },
    )


def public_form_success_view(request, token):
    form_obj = PublicForm.objects.filter(Q(token=token) | Q(custom_slug=token), is_active=True).first()
    if not form_obj:
        raise Http404()
    return render(request, 'public_screen/public_form_success.html', {'form_obj': form_obj})


def public_form_failed_view(request, token):
    form_obj = PublicForm.objects.filter(Q(token=token) | Q(custom_slug=token), is_active=True).first()
    if not form_obj:
        raise Http404()
    return render(request, 'public_screen/public_form_failed.html', {'form_obj': form_obj})
