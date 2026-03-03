from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import get_user_model

from techday.utils import send_email_async, get_styled_email_html

from attendance.models import Attendance
from groups.models import Group
from students.models import Student, StudentRegistration
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback
from dashboard.models import EventSettings, AdminLog


User = get_user_model()


def public_screen_view(request):
    now = timezone.localtime()
    event = EventSettings.get_solo()
    total_students = Student.objects.count()
    is_full = event.max_students is not None and total_students >= event.max_students
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
        school = (request.POST.get('school') or '').strip()
        education_admin = (request.POST.get('education_admin') or '').strip()
        grade = (request.POST.get('grade') or '').strip()
        interests = (request.POST.get('interests') or '').strip()
        if not full_name_ar or not full_name_en or not email or not phone_number or not school or not education_admin or not grade:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة في نموذج التسجيل.')
            return redirect('public_screen:public_screen')
        existing_pending = StudentRegistration.objects.filter(
            Q(email__iexact=email) | Q(phone_number=phone_number),
            status=StudentRegistration.Status.PENDING,
        ).exists()
        if existing_pending:
            messages.info(request, 'طلب التسجيل لهذا البريد أو رقم الهاتف قيد المراجعة بالفعل.')
            return redirect('public_screen:public_screen')
        registration = StudentRegistration.objects.create(
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
    total_present = Student.objects.filter(checked_in=True).count()
    groups = Group.objects.all()
    best_groups = Group.objects.all().order_by('-points')[:5]
    sessions = WorkshopSession.objects.select_related('workshop', 'group').all()
    periods = WorkshopSession.PERIOD_CHOICES

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
        stats_by_admin = Student.objects.values('education_admin').annotate(
            count=Count('id'),
            checked_in_count=Count('id', filter=Q(checked_in=True))
        ).order_by('-count')

        # Stats by Grade
        grade_map = {
            '4-prim': 'الرابع الابتدائي', '5-prim': 'الخامس الابتدائي', '6-prim': 'السادس الابتدائي',
            '1-prep': 'الأول الإعدادي', '2-prep': 'الثاني الإعدادي', '3-prep': 'الثالث الإعدادي',
            '1-sec': 'الأول الثانوي', '2-sec': 'الثاني الثانوي', '3-sec': 'الثالث الثانوي',
        }
        stats_by_grade_raw = Student.objects.values('grade').annotate(count=Count('id')).order_by('grade')
        for item in stats_by_grade_raw:
            stats_by_grade.append({
                'name': grade_map.get(item['grade'], item['grade'] or 'غير محدد'),
                'count': item['count']
            })
        
        # Top Students
        top_points_students = Student.objects.select_related('group').order_by('-points')[:10]

        # Top Rated Workshops
        top_workshops_raw = Workshop.objects.annotate(
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

        total_feedbacks = WorkshopFeedback.objects.count()

        certificates_sent = Student.objects.filter(cert_emails_sent__gt=0).exists()

        # Volunteers
        volunteers_raw = User.objects.filter(role=User.Roles.VOLUNTEER).values_list('first_name', 'last_name')
        volunteers = [f"{v[0]} {v[1]}" for v in volunteers_raw if v[0]]

    current_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(start_time__lte=now.time(), end_time__gte=now.time())
        .first()
    )
    next_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(start_time__gt=now.time())
        .order_by('start_time')
        .first()
    )

    education_admins = [
        'بنها', 'طوخ', 'كفر شكر', 'شبين القناطر', 'الخانكة', 'قها',
        'قليوب', 'القناطر الخيرية', 'غرب شبرا الخيمة', 'شرق شبرا الخيمة',
        'الخصوص', 'العبور',
    ]

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
        'sessions': sessions,
        'periods': periods,
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
    }
    return render(request, 'public_screen/public_screen.html', context)


def registration_success_view(request):
    return render(request, 'public_screen/registration_success.html')
