import io
import ssl
from types import SimpleNamespace
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from weasyprint import HTML, CSS

from techday.utils import send_email_async, get_styled_email_html, send_registration_confirmation_email

from attendance.models import Attendance
from dashboard.models import Notification, Event, StudentSupportRequest
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback, WorkshopResource

from .models import Student, Badge, StudentBadge, StudentEventStats, StudentRegistration, StudentWorkshopNote


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
    current_event = Event.get_current()

    is_registered_for_current_event = False
    if current_event:
        is_registered_for_current_event = StudentRegistration.objects.filter(
            student=student,
            event=current_event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()
    
    # Get participation history from registrations (and attach stats if available)
    stats_by_event_id = {
        s.event_id: s for s in student.event_stats.select_related('event').all()
    }
    approved_regs = (
        StudentRegistration.objects.filter(
            student=student,
            status=StudentRegistration.Status.APPROVED,
        )
        .select_related('event')
        .order_by('-approved_at', '-created_at')
    )
    past_events = []
    seen_event_ids = set()
    for reg in approved_regs:
        if not reg.event_id:
            continue
        if current_event and reg.event_id == current_event.id:
            continue
        if reg.event_id in seen_event_ids:
            continue
        seen_event_ids.add(reg.event_id)
        stats = stats_by_event_id.get(reg.event_id)
        past_events.append(stats or SimpleNamespace(event=reg.event, points=0))
    for event_id, stats in stats_by_event_id.items():
        if current_event and event_id == current_event.id:
            continue
        if event_id in seen_event_ids:
            continue
        past_events.append(stats)
    
    # Get student's badges for CURRENT event
    student_badges = student.badges.filter(badge__event=current_event).select_related('badge').order_by('-earned_at')
    unseen_badges_count = student_badges.filter(is_seen_by_student=False).count()
    
    now = timezone.localtime()
    current_session = None
    next_session = None
    
    notifications = Notification.objects.none()
    if current_event and is_registered_for_current_event and student.group and getattr(student.group, 'event_id', None) == current_event.id:
        notifications = Notification.objects.filter(event=current_event, is_active=True).filter(
            Q(target=Notification.Target.ALL)
            | Q(target=Notification.Target.GROUP, group=student.group)
        ).order_by('-created_at')[:10]
    
    attendance_qs = Attendance.objects.none()
    if current_event and is_registered_for_current_event:
        attendance_qs = Attendance.objects.filter(
            student=student,
            session__group__event=current_event,
        ).select_related('session__workshop')
    attendance_by_session = {a.session_id: a for a in attendance_qs}
    group_sessions = []
    if current_event and is_registered_for_current_event and student.group and getattr(student.group, 'event_id', None) == current_event.id:
        # Get all sessions for current group
        group_sessions = list(
            WorkshopSession.objects.filter(group=student.group)
            .select_related('workshop')
            .order_by('start_time')
        )
        
        # Add any OTHER sessions the student attended (in case of group change during the event)
        attended_session_ids = [s.id for s in group_sessions]
        other_attended_sessions = list(
            WorkshopSession.objects.filter(attendance_records__student=student, group__event=current_event)
            .exclude(id__in=attended_session_ids)
            .select_related('workshop')
            .order_by('start_time')
        )
        if other_attended_sessions:
            group_sessions.extend(other_attended_sessions)
            # Re-sort the combined list by start_time
            group_sessions.sort(key=lambda x: x.start_time)

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
    # Count both present and late as "attended" for statistics
    attended_count = attendance_qs.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_qs.filter(status=Attendance.Status.LATE).count()
    absent_count = attendance_qs.filter(status=Attendance.Status.ABSENT).count()
    
    # Combined count for the progress bar and "0/4" display
    completed_count = attended_count + late_count
    remaining_count = max(0, total_sessions - (completed_count + absent_count))
    
    attendance_rate = 0
    if total_sessions > 0 and completed_count > 0:
        attendance_rate = int(completed_count * 100 / total_sessions)

    # التقييمات التي قام بها الطالب بالفعل
    feedbacks = WorkshopFeedback.objects.filter(student=student).select_related('workshop')
    feedbacks_by_workshop = {f.workshop_id: f for f in feedbacks}
    
    # إضافة التقييم لكل جلسة في القائمة
    for session in group_sessions:
        session.feedback = feedbacks_by_workshop.get(session.workshop_id)

    # ورش حضرها الطالب لإتاحة تقييمها أو تعديله (بما في ذلك الحضور المتأخر)
    attended_workshop_ids = attendance_qs.filter(
        status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
    ).values_list('session__workshop_id', flat=True)
    
    # جميع الورش التي حضرها الطالب لتظهر في قسم التقييم (سواء قيمها أو لا)
    all_attended_workshops = Workshop.objects.filter(
        id__in=attended_workshop_ids
    )
    
    # إضافة التقييم الحالي والمذكرات لكل ورشة في قائمة الحضور
    student_notes = StudentWorkshopNote.objects.filter(student=student).select_related('workshop')
    notes_by_workshop = {n.workshop_id: n for n in student_notes}
    
    # ربط المذكرات والتقييمات بكل جلسة في القائمة لتسهيل العرض المباشر
    for session in group_sessions:
        session.existing_feedback = feedbacks_by_workshop.get(session.workshop_id)
        session.existing_note = notes_by_workshop.get(session.workshop_id)

    # جميع الورش التي حضرها الطالب لتظهر في الأقسام السفلية (كاحتياطي)
    for workshop in all_attended_workshops:
        workshop.existing_feedback = feedbacks_by_workshop.get(workshop.id)
        workshop.existing_note = notes_by_workshop.get(workshop.id)

    event_stats = None
    if current_event and is_registered_for_current_event:
        event_stats, _ = StudentEventStats.objects.get_or_create(student=student, event=current_event)
    
    # نقاط الطالب في الفعالية الحالية بدلاً من النقاط العامة
    current_points = event_stats.points if event_stats else 0

    # ترتيب الطالب في لوحة الشرف (خاص بالفعالية الحالية)
    rank = 0
    if current_event and is_registered_for_current_event:
        rank = StudentEventStats.objects.filter(event=current_event, points__gt=current_points).count() + 1

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
        
    # طلبات الدعم الخاصة بالطالب
    support_requests = student.support_requests.all().order_by('-created_at')

    # لوحة الشرف - أفضل الطلاب (خاص بالفعالية الحالية)
    top_stats = StudentEventStats.objects.none()
    if current_event:
        top_stats = StudentEventStats.objects.filter(event=current_event, points__gt=0).select_related('student', 'student__group').order_by('-points')[:10]
    
    # لوحة الشرف - أفضل المجموعات (خاص بالفعالية الحالية)
    from groups.models import Group
    top_groups = Group.objects.none()
    if current_event:
        top_groups = Group.objects.filter(event=current_event, points__gt=0).order_by('-points')[:10]

    context = {
        'student': student,
        'current_event': current_event,
        'past_events': past_events,
        'current_session': current_session,
        'next_session': next_session,
        'notifications': notifications,
        'group_sessions': group_sessions,
        'total_sessions': total_sessions,
        'attended_count': attended_count, # Just PRESENT
        'completed_count': completed_count, # PRESENT + LATE for progress
        'late_count': late_count,
        'absent_count': absent_count,
        'remaining_count': remaining_count,
        'attendance_rate': attendance_rate,
        'all_attended_workshops': all_attended_workshops,
        'rank': rank,
        'current_points': current_points,
        'group_rank': group_rank,
        'violations': violations,
        'event': current_event, # For backward compatibility in templates
        'resources': resources,
        'student_badges': student_badges,
        'unseen_badges_count': unseen_badges_count,
        'support_requests': support_requests,
        'support_categories': StudentSupportRequest.Category.choices,
        'is_registered_for_current_event': is_registered_for_current_event,
        'top_stats': top_stats,
        'top_groups': top_groups,
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
def register_current_event(request):
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    event = Event.get_current()
    if not event:
        messages.error(request, 'لا توجد فعالية نشطة حالياً.')
        return redirect('students:detail', pk=student.pk)

    if not event.allow_existing_students_registration:
        messages.error(request, 'التسجيل عبر حسابات الطلاب الحاليين غير متاح حالياً.')
        return redirect('students:detail', pk=student.pk)
    
    if event.is_registration_closed or event.is_finished:
        messages.error(request, 'عذراً، باب التسجيل في هذه الفعالية مغلق حالياً.')
        return redirect('students:detail', pk=student.pk)
        
    already_registered = StudentRegistration.objects.filter(
        student=student,
        event=event,
        status=StudentRegistration.Status.APPROVED,
        removed_at__isnull=True,
    ).exists()
    
    if already_registered:
        messages.info(request, 'أنت مسجل بالفعل في هذه الفعالية.')
        return redirect('students:detail', pk=student.pk)
    
    # بدلاً من التسجيل المباشر، نحول الطالب لصفحة تأكيد البيانات
    return redirect('students:event_confirmation')


@login_required
def event_confirmation(request):
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    event = Event.get_current()
    if not event:
        messages.error(request, 'لا توجد فعالية نشطة حالياً.')
        return redirect('students:detail', pk=student.pk)

    if not event.allow_existing_students_registration:
        messages.error(request, 'التسجيل عبر حسابات الطلاب الحاليين غير متاح حالياً.')
        return redirect('students:detail', pk=student.pk)
    
    # التحقق من أن الطالب لم يسجل بالفعل
    if StudentRegistration.objects.filter(
        student=student,
        event=event,
        status=StudentRegistration.Status.APPROVED,
        removed_at__isnull=True,
    ).exists():
        return redirect('students:detail', pk=student.pk)
        
    return render(request, 'students/event_confirmation.html', {
        'student': student,
        'event': event,
    })


@login_required
def confirm_registration(request):
    if request.method != 'POST':
        return redirect('students:event_confirmation')
        
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    event = Event.get_current()
    if not event or event.is_registration_closed or event.is_finished:
        messages.error(request, 'عذراً، باب التسجيل مغلق حالياً.')
        return redirect('students:detail', pk=student.pk)
        
    already_registered = StudentRegistration.objects.filter(
        student=student,
        event=event,
        status=StudentRegistration.Status.APPROVED,
        removed_at__isnull=True,
    ).exists()
    
    if already_registered:
        messages.info(request, 'أنت مسجل بالفعل في هذه الفعالية.')
        return redirect('students:detail', pk=student.pk)
        
    # تسجيل الطالب في الفعالية
    StudentRegistration.objects.create(
        event=event,
        student=student,
        full_name_ar=student.name,
        email=student.email,
        phone_number=student.phone_number,
        school=student.school,
        education_admin=student.education_admin,
        grade=student.grade,
        status=StudentRegistration.Status.APPROVED,
        approved_at=timezone.now()
    )
    
    # تهيئة إحصائيات الطالب لهذه الفعالية
    StudentEventStats.objects.get_or_create(student=student, event=event)
    
    # إرسال تفاصيل الفعالية والـ QR
    send_registration_confirmation_email(student, event)
    
    messages.success(request, 'تم حجز مكانك في الفعالية بنجاح! تم إرسال رمز الـ QR وتفاصيل الفعالية إلى بريدك الإلكتروني.')
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
    
    event = Event.get_current()
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
    
    event = Event.get_current()
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
def submit_workshop_note(request):
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return redirect('dashboard:admin_dashboard')
    
    if request.method == 'POST':
        workshop_id = request.POST.get('workshop_id')
        content = request.POST.get('content', '').strip()
        
        if not content:
            messages.error(request, 'يرجى كتابة الملاحظة قبل الحفظ.')
        else:
            StudentWorkshopNote.objects.update_or_create(
                student=student,
                workshop_id=workshop_id,
                defaults={'content': content}
            )
            messages.success(request, 'تم حفظ مذكرة التعلم بنجاح.')
            
    return redirect('students:detail', pk=student.pk)


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
        'event': Event.get_current(),
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
