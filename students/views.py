import io
import ssl
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from weasyprint import HTML, CSS

from attendance.models import Attendance
from dashboard.models import Notification, EventSettings, StudentSupportRequest
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback, WorkshopResource

from .models import Student, Badge, StudentBadge


@login_required
def mark_badges_seen(request):
    if request.method == 'POST':
        student = getattr(request.user, 'student_profile', None)
        if student:
            StudentBadge.objects.filter(student=student, is_seen_by_student=False).update(is_seen_by_student=True)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
def student_list(request):
    students = Student.objects.select_related('group').all()
    return render(request, 'students/list.html', {'students': students})


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('group'), pk=pk)
    
    # Get student's badges
    student_badges = student.badges.select_related('badge').order_by('-earned_at')
    unseen_badges_count = student_badges.filter(is_seen_by_student=False).count()
    
    now = timezone.localtime()
    current_session = None
    next_session = None
    notifications = Notification.objects.filter(is_active=True).filter(
        Q(target=Notification.Target.ALL)
        | Q(target=Notification.Target.GROUP, group=student.group)
    ).order_by('-created_at')[:10]
    attendance_qs = Attendance.objects.filter(student=student).select_related('session__workshop')
    attendance_by_session = {a.session_id: a for a in attendance_qs}
    group_sessions = []
    if student.group:
        group_sessions = list(
            WorkshopSession.objects.filter(group=student.group)
            .select_related('workshop')
            .order_by('start_time')
        )
        for session in group_sessions:
            record = attendance_by_session.get(session.id)
            if record:
                session.attendance_status = record.get_status_display()
                session.attendance_status_value = record.status
            else:
                session.attendance_status = 'لم يتم التسجيل'
                session.attendance_status_value = 'none'
        current_session = (
            WorkshopSession.objects.filter(
                group=student.group,
                start_time__lte=now.time(),
                end_time__gte=now.time(),
            )
            .select_related('workshop')
            .first()
        )
        next_session = (
            WorkshopSession.objects.filter(group=student.group, start_time__gt=now.time())
            .select_related('workshop', 'workshop__supervisor')
            .order_by('start_time')
            .first()
        )
    total_sessions = len(group_sessions)
    attended_count = attendance_qs.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_qs.filter(status=Attendance.Status.LATE).count()
    absent_count = attendance_qs.filter(status=Attendance.Status.ABSENT).count()
    attendance_rate = 0
    if total_sessions > 0 and attended_count > 0:
        attendance_rate = int(attended_count * 100 / total_sessions)

    # التقييمات التي قام بها الطالب بالفعل
    feedbacks = WorkshopFeedback.objects.filter(student=student).select_related('workshop')
    feedbacks_by_workshop = {f.workshop_id: f for f in feedbacks}
    
    # إضافة التقييم لكل جلسة في القائمة
    for session in group_sessions:
        session.feedback = feedbacks_by_workshop.get(session.workshop_id)

    # ورش حضرها الطالب لإتاحة تقييمها أو تعديله
    attended_workshop_ids = attendance_qs.filter(status=Attendance.Status.PRESENT).values_list('session__workshop_id', flat=True)
    
    # جميع الورش التي حضرها الطالب لتظهر في قسم التقييم (سواء قيمها أو لا)
    all_attended_workshops = Workshop.objects.filter(
        id__in=attended_workshop_ids
    )
    
    # إضافة التقييم الحالي لكل ورشة (إن وجد) لتسهيل العرض في القالب
    for workshop in all_attended_workshops:
        workshop.existing_feedback = feedbacks_by_workshop.get(workshop.id)

    # ترتيب الطالب في لوحة الشرف
    rank = Student.objects.filter(points__gt=student.points).count() + 1

    # المصادر التعليمية المتاحة للطالب (من الورش التي يحضرها)
    workshop_ids = [session.workshop_id for session in group_sessions]
    resources = WorkshopResource.objects.filter(workshop_id__in=workshop_ids).select_related('workshop')
    
    # مخالفات الطالب
    violations = student.violations.all().order_by('-created_at')
    
    # ترتيب المجموعة
    group_rank = 0
    if student.group:
        from groups.models import Group
        group_rank = Group.objects.filter(points__gt=student.group.points).count() + 1
        
    event = EventSettings.get_solo()

    # طلبات الدعم الخاصة بالطالب
    support_requests = student.support_requests.all().order_by('-created_at')

    context = {
        'student': student,
        'current_session': current_session,
        'next_session': next_session,
        'notifications': notifications,
        'group_sessions': group_sessions,
        'total_sessions': total_sessions,
        'attended_count': attended_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'attendance_rate': attendance_rate,
        'all_attended_workshops': all_attended_workshops,
        'rank': rank,
        'group_rank': group_rank,
        'violations': violations,
        'event': event,
        'resources': resources,
        'student_badges': student_badges,
        'unseen_badges_count': unseen_badges_count,
        'support_requests': support_requests,
        'support_categories': StudentSupportRequest.Category.choices,
    }
    return render(request, 'students/detail.html', context)


@login_required
def student_submit_support_request(request):
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    if request.method == 'POST':
        category = request.POST.get('category')
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not subject or not message:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة.')
        else:
            StudentSupportRequest.objects.create(
                student=student,
                category=category,
                subject=subject,
                message=message
            )
            messages.success(request, 'تم إرسال طلبك بنجاح، سيقوم فريق الدعم بمراجعته والرد عليك قريباً.')
            
    return redirect('students:detail', pk=student.pk)


@login_required
def update_phone_view(request):
    # الحصول على ملف الطالب
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    # إذا كان لديه رقم هاتف بالفعل، يوجهه للرئيسية
    if student.phone_number:
        return redirect('students:detail', pk=student.pk)
        
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        if phone_number:
            student.phone_number = phone_number
            student.save()
            messages.success(request, 'تم تحديث رقم هاتفك بنجاح، أهلاً بك!')
            return redirect('students:detail', pk=student.pk)
        else:
            messages.error(request, 'يرجى إدخال رقم هاتف صحيح.')
            
    return render(request, 'students/update_phone.html', {'student': student})


def student_verify(request, identifier):
    student = (
        Student.objects.filter(student_id=identifier).select_related('group').first()
        or (
            Student.objects.filter(id=identifier).select_related('group').first()
            if identifier.isdigit()
            else None
        )
    )
    if not student:
        return render(request, '400.html', status=404)
    
    # التحقق من أهلية الطالب لعرض صفحة التحقق (نفس شروط الشهادة)
    if student.is_certificate_banned:
        return render(request, '403.html', {'message': 'عذراً، صفحة التحقق محجوبة لهذا الطالب بسبب مخالفات إدارية.'}, status=403)
    
    if not student.checked_in:
        return render(request, '403.html', {'message': 'عذراً، يجب تسجيل حضور الطالب للفعالية أولاً ليتم تفعيل صفحة التحقق.'}, status=403)
    
    event = EventSettings.get_solo()
    attendance_qs = Attendance.objects.filter(
        student=student,
        status=Attendance.Status.PRESENT,
    ).select_related('session__workshop')
    present_count = attendance_qs.count()
    attended_workshops = list(
        attendance_qs.order_by('session__start_time')
        .values_list('session__workshop__title', flat=True)
        .distinct()
    )

    assigned_sessions_count = 0
    assigned_workshops = []
    attendance_rate = 0
    if student.group:
        group_sessions_qs = WorkshopSession.objects.filter(group=student.group).select_related('workshop').order_by('start_time')
        assigned_sessions_count = group_sessions_qs.count()
        assigned_workshops = list(
            group_sessions_qs.values_list('workshop__title', flat=True).distinct()
        )
    
    # إذا كان الإجمالي المقرر صفراً (طالب بدون مجموعة أو مجموعة بدون جلسات)، نستخدم أقصى عدد جلسات مخصص لأي مجموعة كمرجع
    if assigned_sessions_count == 0:
        from django.db.models import Count
        max_sessions = WorkshopSession.objects.values('group').annotate(c=Count('id')).order_by('-c').first()
        if max_sessions:
            assigned_sessions_count = max_sessions['c']
    
    # ضمان أن الإجمالي المقرر لا يقل عن عدد الجلسات التي حضرها الطالب فعلياً
    if present_count > assigned_sessions_count:
        assigned_sessions_count = present_count
        
    # حساب نسبة الحضور النهائية
    if assigned_sessions_count > 0:
        attendance_rate = int((present_count / assigned_sessions_count) * 100)

    return render(
        request,
        'students/verify.html',
        {
            'student': student,
            'event': event,
            'present_count': present_count,
            'attended_workshops': attended_workshops,
            'assigned_sessions_count': assigned_sessions_count,
            'assigned_workshops': assigned_workshops,
            'attendance_rate': attendance_rate,
        },
    )


def student_certificate(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    if student.is_certificate_banned:
        return render(request, '403.html', {'message': 'الشهادة محجوبة'}, status=403)
    if not student.checked_in:
        return render(request, '403.html', {'message': 'يجب تسجيل الحضور أولاً'}, status=403)
    
    event = EventSettings.get_solo()
    student_identifier = student.student_id or student.id
    qr_payload = f'https://verify.edutech-egy.com/td/{student_identifier}'
    
    return render(
        request, 
        'students/certificate.html', 
        {
            'student': student,
            'event': event,
            'qr_payload': qr_payload,
        }
    )


@login_required
def send_certificate_email(request, pk):
    student = get_object_or_404(Student, pk=pk)
    
    # التحقق من أن المستخدم هو صاحب الملف الشخصي أو مدير
    if not request.user.is_staff and getattr(request.user, 'student_profile', None) != student:
        messages.error(request, "ليس لديك صلاحية للقيام بهذا الإجراء.")
        return redirect('students:detail', pk=pk)
    
    # التحقق من الأهلية للشهادة
    if student.is_certificate_banned:
        messages.error(request, "عذراً، الشهادة محجوبة عنك بسبب مخالفات إدارية.")
        return redirect('students:detail', pk=pk)
    
    if not student.checked_in:
        messages.error(request, "يجب تسجيل حضور الفعالية أولاً للحصول على الشهادة.")
        return redirect('students:detail', pk=pk)

    # التحقق من عدد المحاولات (3 مرات كحد أقصى)
    if student.cert_emails_sent >= 3:
        messages.error(request, "لقد استنفدت الحد الأقصى لإرسال الشهادة (3 مرات).")
        return redirect('students:detail', pk=pk)
    
    # التحقق من مرور 24 ساعة منذ آخر محاولة
    if student.last_cert_email_at:
        wait_until = student.last_cert_email_at + timezone.timedelta(hours=24)
        if timezone.now() < wait_until:
            wait_time = wait_until - timezone.now()
            hours = wait_time.seconds // 3600
            minutes = (wait_time.seconds // 60) % 60
            messages.warning(request, f"يرجى الانتظار {hours} ساعة و {minutes} دقيقة لإرسال الشهادة مرة أخرى.")
            return redirect('students:detail', pk=pk)
            
    # إعداد الإيميل
    subject = f"شهادة حضور فعالية Tech Day - {student.name}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = student.email if student.email else request.user.email
    
    if not to_email:
        messages.error(request, "لا يوجد بريد إلكتروني مسجل لإرسال الشهادة إليه.")
        return redirect('students:detail', pk=pk)
        
    context = {
        'student': student,
        'event': EventSettings.get_solo(),
        'site_url': settings.SITE_BASE_URL,
    }
    
    html_content = render_to_string('students/emails/certificate_email.html', context)
    text_content = strip_tags(html_content)
    
    # إنشاء ملف PDF للشهادة
    student_identifier = student.student_id or student.id
    qr_payload = f'https://verify.edutech-egy.com/td/{student_identifier}'
    
    certificate_context = {
        'student': student,
        'event': context['event'],
        'qr_payload': qr_payload,
    }
    # نحتاج لمعالجة مسارات Static في PDF، سنستخدم SITE_BASE_URL للوصول للملفات
    cert_html = render_to_string('students/certificate.html', certificate_context)
    
    # تحويل الروابط النسبية لروابط مطلقة لـ WeasyPrint
    base_url = request.build_absolute_uri('/')
    pdf_file = io.BytesIO()
    HTML(string=cert_html, base_url=base_url).write_pdf(pdf_file)
    pdf_file.seek(0)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    
    # إرفاق ملف PDF
    msg.attach(f"Certificate_{student.student_id}.pdf", pdf_file.read(), "application/pdf")
    
    try:
        msg.send()
        # تحديث بيانات الطالب
        student.cert_emails_sent += 1
        student.last_cert_email_at = timezone.now()
        student.save()
        
        messages.success(request, f"تم إرسال الشهادة بنجاح إلى البريد: {to_email}")
    except Exception as e:
        messages.error(request, f"حدث خطأ أثناء إرسال البريد: {str(e)}")
        
    return redirect('students:detail', pk=pk)
