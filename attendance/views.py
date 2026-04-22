from datetime import datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone

from techday.utils import send_email_async, get_styled_email_html
from students.models import Student, Badge, StudentBadge, StudentEventStats, StudentRegistration
from students.utils import check_and_award_badges
from groups.models import Group
from users.models import User
from workshops.models import WorkshopSession, WorkshopFeedback
from dashboard.models import VolunteerNote, AdminLog, StudentViolation, Event

from .models import Attendance


def require_attendance_staff(user):
    return user.is_authenticated and (
        user.is_admin() or user.is_supervisor() or user.is_volunteer()
    )


@login_required
def volunteer_dashboard(request):
    if not request.user.is_volunteer() and not request.user.is_admin():
        return HttpResponseForbidden()
    recent_violations = (
        StudentViolation.objects.filter(reported_by=request.user)
        .select_related('student')
        .order_by('-created_at')[:10]
    )
    return render(
        request,
        'attendance/volunteer_dashboard.html',
        {
            'recent_violations': recent_violations,
        },
    )


def _send_attendance_email(student, session, workshop_title, now):
    email = student.email or ''
    if not email:
        return
    subject = 'تأكيد حضورك في فعالية Tech Day – EduTech Egypt'
    name = student.name
    workshop_room = session.workshop.room if session else ''
    group_code = student.group.code if student.group else ''
    period_display = session.get_period_display() if session else ''
    text_body_lines = [
        f'مرحبًا {name},',
        '',
        'تم تسجيل حضورك بنجاح في فعالية Tech Day – الفريق التقني بالقليوبية.',
        '',
        f'المجموعة: {group_code}' if group_code else '',
        f'الورشة الحالية: {workshop_title}' if workshop_title else '',
        f'القاعة: {workshop_room}' if workshop_room else '',
        f'الفترة: {period_display}' if period_display else '',
        '',
        'تعليمات اليوم:',
        '- التزم بالتواجد في القاعة المحددة طوال زمن الورشة.',
        '- تأكد من متابعة تعليمات المشرف والمنظمين.',
        '- في حال وجود أي استفسار يمكنك التوجه لفريق الدعم في القاعة الرئيسية.',
        '',
        'شكرًا لمشاركتك في Tech Day ونتمنى لك تجربة مفيدة وممتعة.',
        '',
        'تحياتنا،',
        'EduTech Egypt System',
    ]
    text_body = '\n'.join([line for line in text_body_lines if line != ''])
    
    details_html = ""
    if group_code:
        details_html += f'<tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;width:120px;">المجموعة</td><td style="padding:8px 0;font-size:14px;font-family:monospace;color:#22d3ee;font-weight:700;">{group_code}</td></tr>'
    if workshop_title:
        details_html += f'<tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;">الورشة</td><td style="padding:8px 0;font-size:14px;color:#e5e7eb;">{workshop_title}</td></tr>'
    if workshop_room:
        details_html += f'<tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;">القاعة</td><td style="padding:8px 0;font-size:14px;color:#e5e7eb;">{workshop_room}</td></tr>'
    if period_display:
        details_html += f'<tr><td style="padding:8px 0;font-size:13px;color:#94a3b8;">الفترة</td><td style="padding:8px 0;font-size:14px;color:#e5e7eb;">{period_display}</td></tr>'

    content_blocks = f"""
        <div class="td-email-box" style="padding:20px;border-radius:20px;background-color:#0f172a;border:1px solid #1e293b;margin-bottom:20px;">
          <p class="td-email-text-main" style="margin:0 0 15px;font-size:14px;color:#22d3ee;font-weight:700;">✅ تفاصيل تسجيل الحضور</p>
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
            {details_html}
          </table>
        </div>
        <div class="td-email-box" style="padding:20px;border-radius:20px;background-color:#0f172a;border:1px solid #1e293b;">
          <p class="td-email-text-main" style="margin:0 0 12px;font-size:14px;color:#e5e7eb;font-weight:700;">📌 تعليمات هامة:</p>
          <ul style="margin:0;padding:0 20px;font-size:13px;color:#cbd5f5;line-height:1.6;">
            <li>الالتزام بالتواجد في القاعة المحددة طوال زمن الورشة.</li>
            <li>اتباع تعليمات مشرف الورشة والمنظمين بدقة.</li>
            <li>لأي استفسار يمكنك التوجه لفريق الدعم في القاعة الرئيسية.</li>
          </ul>
        </div>
    """
    
    html_body = get_styled_email_html(
        subject=subject,
        preview_text="تم تسجيل حضورك بنجاح في فعالية Tech Day",
        title="✅ تأكيد تسجيل الحضور",
        main_text=f"مرحبًا {name}، تم تسجيل دخولك للفعالية بنجاح.",
        content_blocks_html=content_blocks
    )

    from django.core.mail import EmailMultiAlternatives
    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    message.attach_alternative(html_body, 'text/html')
    send_email_async(message, 'تأكيد حضور ورشة')


def _register_attendance_for_session(student, session, status_value, event=None):
    now = timezone.localtime()
    workshop_title = ''
    points_awarded = 0
    is_session_already_registered = False
    
    # استخدام الفعالية الممررة أو جلبها من الجلسة أو الحالية
    if not event:
        event = (session.workshop.event if session and session.workshop.event else Event.get_current())
    
    if not event:
        # تأمين إضافي لضمان عدم وجود قيمة null
        event = Event.get_current()
    
    if not event:
        raise ValueError("لا يمكن العثور على فعالية صالحة لتسجيل الحضور. يرجى إنشاء فعالية أولاً.")
    
    # الحصول على إحصائيات الطالب لهذه الفعالية أو إنشاء واحدة
    stats = StudentEventStats.objects.filter(student=student, event=event).first()
    if not stats:
        stats = StudentEventStats.objects.create(student=student, event=event)

    # التحقق إذا كان الطالب سجل حضور من قبل في الفعالية (checked_in)
    is_event_already_checked_in = stats.checked_in

    if session:
        # Check if attendance already exists
        attendance = Attendance.objects.filter(student=student, session=session).first()
        is_session_already_registered = attendance is not None
        
        if not is_session_already_registered:
            attendance = Attendance.objects.create(
                student=student,
                session=session,
                status=status_value,
                scanned_at=now,
            )
            # إضافة نقاط للطالب وللمجموعة عند أول تسجيل حضور للجلسة (إذا كان ذلك مسموحاً)
            if status_value == Attendance.Status.PRESENT:
                points_awarded = session.workshop.points_per_session
                # تحديث النقاط العامة للطالب
                student.points += points_awarded
                student.save(update_fields=['points'])
                
                # تحديث النقاط الخاصة بالفعالية
                stats.points += points_awarded
                stats.save(update_fields=['points'])
                
                # التحقق من إعدادات الفعالية للسماح بنقاط المجموعات (للمجموعة في نفس الفعالية)
                if student.group and student.group.event == event and event.allow_group_points:
                    student.group.points += points_awarded
                    student.group.save(update_fields=['points'])
        else:
            # إذا كانت موجودة بالفعل، نحدث الحالة فقط
            old_status = attendance.status
            if old_status != status_value:
                attendance.status = status_value
                attendance.save()
                
                # تحديث النقاط إذا تغيرت الحالة من غائب/متأخر إلى حاضر
                if old_status != Attendance.Status.PRESENT and status_value == Attendance.Status.PRESENT:
                    points_awarded = session.workshop.points_per_session
                    student.points += points_awarded
                    student.save(update_fields=['points'])
                    stats.points += points_awarded
                    stats.save(update_fields=['points'])
                    if student.group and student.group.event == event and event.allow_group_points:
                        student.group.points += points_awarded
                        student.group.save(update_fields=['points'])
                
                # خصم النقاط إذا تغيرت الحالة من حاضر إلى غائب/متأخر
                elif old_status == Attendance.Status.PRESENT and status_value != Attendance.Status.PRESENT:
                    points_to_remove = session.workshop.points_per_session
                    student.points = max(0, student.points - points_to_remove)
                    student.save(update_fields=['points'])
                    stats.points = max(0, stats.points - points_to_remove)
                    stats.save(update_fields=['points'])
                    if student.group and student.group.event == event and event.allow_group_points:
                        student.group.points = max(0, student.group.points - points_to_remove)
                        student.group.save(update_fields=['points'])

        workshop_title = session.workshop.title

    if not is_event_already_checked_in:
        # تحديث حالة الدخول في الموديلين (العام والخاص بالفعالية)
        student.checked_in = True
        student.checked_in_at = now
        student.save(update_fields=['checked_in', 'checked_in_at'])
        
        stats.checked_in = True
        stats.checked_in_at = now
        stats.save(update_fields=['checked_in', 'checked_in_at'])
        
        _send_attendance_email(student, session, workshop_title, now)
    
    # Check and award badges after attendance/points change (specific to this event)
    new_badges = check_and_award_badges(student, event=event)
    
    return workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered, new_badges


@login_required
def scan_qr(request):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    
    event = Event.get_current()
    if not event:
        return JsonResponse(
            {
                'success': False,
                'message': 'لا توجد فعالية نشطة حالياً في النظام. يرجى مراجعة الإدارة.',
            }
        )
        
    if request.method == 'POST':
        if event and not event.allow_group_points and not request.user.is_admin():
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، إضافة النقاط مغلقة حالياً بقرار من الإدارة.',
                }
            )
            
        student_id = request.POST.get('student_id')
        status_value = request.POST.get('status') or Attendance.Status.PRESENT
        
        student = Student.objects.filter(student_id=student_id).first()
        if not student:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، لم يتم العثور على طالب بهذا الرقم في النظام.',
                }
            )
        
        # التحقق من تسجيل الطالب في الفعالية الحالية
        is_registered = StudentRegistration.objects.filter(
            student=student,
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()
        
        if not is_registered:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، هذا الطالب غير مسجل في هذه الفعالية أو لم تتم الموافقة على طلبه بعد.',
                }
            )
            
        now = timezone.localtime()
        session = None
        if student.group and student.group.event == event:
            # 1. محاولة العثور على الجلسة الحالية
            session = (
                WorkshopSession.objects.filter(
                    group=student.group,
                    start_time__lte=now.time(),
                    end_time__gte=now.time(),
                )
                .select_related('workshop')
                .first()
            )
            
            # 2. إذا لم توجد جلسة حالية، نبحث عن أقرب جلسة (قبل أو بعد بـ 45 دقيقة)
            if not session:
                current_time = now.time()
                # تحويل الوقت الحالي لـ datetime للمقارنة مع فارق زمني
                now_dt = datetime.combine(now.date(), current_time)
                
                # البحث عن جلسة انتهت مؤخراً (خلال 45 دقيقة)
                last_session = WorkshopSession.objects.filter(
                    group=student.group,
                    end_time__lte=current_time,
                ).order_by('-end_time').first()
                
                if last_session:
                    last_end_dt = datetime.combine(now.date(), last_session.end_time)
                    if (now_dt - last_end_dt).total_seconds() <= 45 * 60:
                        session = last_session
                
                # إذا لم نجد جلسة منتهية مؤخراً، نبحث عن الجلسة القادمة (ستبدأ خلال 45 دقيقة)
                if not session:
                    next_session = WorkshopSession.objects.filter(
                        group=student.group,
                        start_time__gte=current_time,
                    ).order_by('start_time').first()
                    
                    if next_session:
                        next_start_dt = datetime.combine(now.date(), next_session.start_time)
                        if (next_start_dt - now_dt).total_seconds() <= 45 * 60:
                            session = next_session

        # منع تسجيل الحضور خارج وقت الورشة للمشرفين والمتطوعين (إلا إذا كان الطالب لم يسجل دخول للفعالية بعد)
        is_admin = request.user.is_superuser or (hasattr(request.user, 'is_admin') and request.user.is_admin())
        
        # إذا لم يتم العثور على جلسة، وكان المستخدم ليس أدمن والطالب مسجل بالفعل بالفعالية، نمنع التسجيل
        if not session and not is_admin:
            stats = StudentEventStats.objects.filter(student=student, event=event).first()
            if stats and stats.checked_in:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'عذراً، لا توجد ورشة نشطة أو قريبة حالياً لمجموعة هذا الطالب، وقد تم تسجيل حضوره بالفعالية مسبقاً.',
                    }
                )
            # إذا لم يكن قد سجل، سنسمح للمتطوع بتسجيل دخوله العام للفعالية (عبر استكمال الكود أدناه)

        # إذا كان أدمن ولم يتم العثور على جلسة حالية، نحاول العثور على أقرب جلسة للطالب في هذه الفعالية
        if not session and is_admin and student.group and student.group.event == event:
            session = WorkshopSession.objects.filter(
                group=student.group
            ).order_by('start_time').first() # نأخذ أول جلسة كمثال أو يمكن تحسينها لاحقاً

        try:
            workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered, new_badges = _register_attendance_for_session(student, session, status_value, event=event)
        except Exception as e:
            return JsonResponse(
                {
                    'success': False,
                    'message': f'حدث خطأ داخلي أثناء تسجيل الحضور: {str(e)}',
                }
            )
        
        # تحديد الرسالة بناءً على نوع المسح
        if session:
            message = 'تم تسجيل الحضور لهذه الورشة مسبقاً' if is_session_already_registered else 'تم تسجيل الحضور بنجاح'
        else:
            message = 'تم تسجيل الحضور بالفعالية بالفعل' if is_event_already_checked_in else 'تم تسجيل الحضور بنجاح'

        return JsonResponse(
            {
                'success': True,
                'is_already_checked_in': is_session_already_registered if session else is_event_already_checked_in,
                'student': student.name,
                'group': student.group.code if student.group else '',
                'workshop': workshop_title,
                'points_awarded': points_awarded,
                'message': message,
                'new_badges': [b.name for b in new_badges] if new_badges else []
            }
        )
    scan_url = reverse('attendance:scan_qr')
    return render(request, 'attendance/scan_qr.html', {'scan_url': scan_url})


@login_required
def scan_session_qr(request, session_id):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    
    event = Event.get_current()
    if not event:
        return JsonResponse(
            {
                'success': False,
                'message': 'لا توجد فعالية نشطة حالياً في النظام. يرجى مراجعة الإدارة.',
            }
        )
        
    session = get_object_or_404(
        WorkshopSession.objects.select_related('workshop', 'group'),
        pk=session_id,
    )
    if request.method == 'POST':
        if event and not event.allow_group_points and not request.user.is_admin():
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، إضافة النقاط مغلقة حالياً بقرار من الإدارة.',
                }
            )
            
        student_id = request.POST.get('student_id')
        status_value = request.POST.get('status') or Attendance.Status.PRESENT
        
        student = Student.objects.filter(student_id=student_id).first()
        if not student:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، لم يتم العثور على طالب بهذا الرقم في النظام.',
                }
            )
        
        # التحقق من تسجيل الطالب في الفعالية الحالية
        is_registered = StudentRegistration.objects.filter(
            student=student,
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()
        
        if not is_registered:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'عذراً، هذا الطالب غير مسجل في هذه الفعالية أو لم تتم الموافقة على طلبه بعد.',
                }
            )
            
        # التحقق من الوقت للجلسة الحالية
        now = timezone.localtime()
        is_admin = request.user.is_superuser or (hasattr(request.user, 'is_admin') and request.user.is_admin())
        if not is_admin and (now.time() < session.start_time or now.time() > session.end_time):
            return JsonResponse(
                {
                    'success': False,
                    'message': f'لا يمكن تسجيل الحضور خارج وقت الجلسة ({session.start_time.strftime("%H:%M")} - {session.end_time.strftime("%H:%M")}).',
                }
            )

        if not student.group or student.group_id != session.group_id:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'هذا الطالب ليس ضمن المجموعة المخصصة لهذه الجلسة.',
                }
            )
        try:
            workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered, new_badges = _register_attendance_for_session(student, session, status_value, event=event)
        except Exception as e:
            return JsonResponse(
                {
                    'success': False,
                    'message': f'حدث خطأ داخلي أثناء تسجيل الحضور: {str(e)}',
                }
            )
            
        return JsonResponse(
            {
                'success': True,
                'is_already_checked_in': is_session_already_registered,
                'student': student.name,
                'group': student.group.code if student.group else '',
                'workshop': workshop_title,
                'points_awarded': points_awarded,
                'message': 'تم تسجيل الحضور لهذه الورشة مسبقاً' if is_session_already_registered else 'تم تسجيل الحضور بنجاح',
                'new_badges': [b.name for b in new_badges] if new_badges else []
            }
        )
    scan_url = reverse('attendance:scan_session_qr', args=[session.id])
    
    # حساب الطلاب الذين سجلوا حضوراً للفعالية (checked_in) ولكنهم لم يسجلوا حضوراً لهذه الورشة بعد
    # نستخدم Q لضمان أننا نختار الطلاب الذين في مجموعة الجلسة، والذين سجلوا حضوراً، وليس لديهم سجل حضور 'PRESENT' لهذه الجلسة
    already_present_ids = Attendance.objects.filter(
        session=session, 
        status=Attendance.Status.PRESENT
    ).values_list('student_id', flat=True)
    
    checked_in_not_present_count = Student.objects.filter(
        group=session.group,
        registrations__event=event,
        registrations__status=StudentRegistration.Status.APPROVED,
        registrations__removed_at__isnull=True,
        checked_in=True
    ).exclude(id__in=already_present_ids).distinct().count()

    return render(
        request,
        'attendance/scan_qr.html',
        {
            'scan_url': scan_url, 
            'session': session,
            'checked_in_not_present_count': checked_in_not_present_count
        },
    )


@login_required
def mark_all_group_present(request, session_id):
    """
    تسجيل حضور جميع طلاب المجموعة (الذين سجلوا حضوراً للفعالية بالفعل) في جلسة محددة بضغطة واحدة.
    """
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    
    if request.method != 'POST':
        return redirect('attendance:scan_session_qr', session_id=session_id)
        
    session = get_object_or_404(WorkshopSession, pk=session_id)
    now = timezone.localtime()
    
    event = Event.get_current()
    
    # الطلاب الذين سجلوا حضوراً للفعالية (checked_in) وفي مجموعة الجلسة وليس لديهم سجل حضور 'PRESENT' لهذه الجلسة
    already_present_ids = Attendance.objects.filter(
        session=session, 
        status=Attendance.Status.PRESENT
    ).values_list('student_id', flat=True)
    
    students_to_mark = Student.objects.filter(
        group=session.group,
        registrations__event=event,
        registrations__status=StudentRegistration.Status.APPROVED,
        registrations__removed_at__isnull=True,
        checked_in=True
    ).exclude(id__in=already_present_ids).distinct()
    
    count = 0
    points_per_session = session.workshop.points_per_session
    
    for student in students_to_mark:
        # تسجيل الحضور أو تحديثه ليكون PRESENT
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            session=session,
            defaults={
                'status': Attendance.Status.PRESENT,
                'scanned_at': now,
            }
        )
        
        # إضافة النقاط فقط إذا كان السجل جديداً أو كانت الحالة السابقة غير PRESENT
        # (ملاحظة: الطلاب المختارون أصلاً هم من ليس لديهم PRESENT لهذه الجلسة)
        
        # الحصول على إحصائيات الطالب لهذه الفعالية
        stats, _ = StudentEventStats.objects.get_or_create(student=student, event=event)
        
        # تحديث النقاط العامة والخاصة بالفعالية
        student.points += points_per_session
        student.save(update_fields=['points'])
        
        stats.points += points_per_session
        stats.save(update_fields=['points'])
        
        # إضافة نقاط للمجموعة فقط إذا كان مسموحاً بذلك في الإعدادات
        if student.group and event.allow_group_points:
            student.group.points += points_per_session
            student.group.save(update_fields=['points'])
            
        # التحقق من الأوسمة (Badge Check) للفعالية الحالية
        check_and_award_badges(student, event=event)
        count += 1
    
    if count > 0:
        messages.success(request, f'تم تسجيل حضور {count} طالب من مجموعة {session.group.code} بنجاح.')
        AdminLog.objects.create(
            action=f'تم تسجيل حضور جماعي ({count} طالب) لمجموعة {session.group.code} في جلسة {session.workshop.title} بواسطة {request.user.username}'
        )
    else:
        messages.info(request, 'لم يتم العثور على طلاب جدد لتسجيل حضورهم (تأكد أنهم سجلوا حضوراً للفعالية أولاً).')
        
    return redirect('attendance:scan_session_qr', session_id=session_id)


@login_required
def volunteer_notes(request):
    """
    View for volunteers and supervisors to submit notes/feedback to the admin.
    """
    is_staff = request.user.is_admin() or request.user.is_volunteer() or request.user.is_supervisor()
    if not is_staff:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        text = (request.POST.get('note') or '').strip()
        if not text:
            messages.error(request, 'برجاء كتابة نص الملاحظة قبل الإرسال.')
        else:
            VolunteerNote.objects.create(author=request.user, text=text)
            messages.success(request, 'تم حفظ الملاحظة بنجاح.')
        return redirect('attendance:volunteer_notes')
    
    # Show user's own notes for today
    today = timezone.localdate()
    user_notes = VolunteerNote.objects.filter(author=request.user, created_at__date=today).order_by('-created_at')
    
    return render(request, 'attendance/volunteer_notes.html', {
        'user_notes': user_notes
    })


@login_required
def volunteer_report_violation(request):
    if not getattr(request.user, 'is_volunteer', lambda: False)() and not getattr(
        request.user, 'is_admin', lambda: False
    )():
        return HttpResponseForbidden()
    if request.method != 'POST':
        return HttpResponseForbidden()
    student_code = (request.POST.get('student_id') or '').strip()
    reason = (request.POST.get('reason') or '').strip()
    if not student_code or not reason:
        messages.error(request, 'برجاء إدخال رقم الطالب وسبب المخالفة.')
        referer = request.META.get('HTTP_REFERER')
        if referer and '/مخالفات-الطلاب/' in referer:
            return redirect('dashboard:admin_student_violations')
        return redirect('attendance:volunteer_dashboard')
    student = Student.objects.filter(student_id=student_code).first()
    if not student:
        messages.error(request, 'لم يتم العثور على طالب بهذا الرقم.')
        referer = request.META.get('HTTP_REFERER')
        if referer and '/مخالفات-الطلاب/' in referer:
            return redirect('dashboard:admin_student_violations')
        return redirect('attendance:volunteer_dashboard')
    StudentViolation.objects.create(
        student=student,
        reported_by=request.user,
        reason=reason,
    )
    messages.success(request, 'تم تسجيل المخالفة وتحويلها للإدارة لمراجعتها.')
    referer = request.META.get('HTTP_REFERER')
    if referer and '/مخالفات-الطلاب/' in referer:
        return redirect('dashboard:admin_student_violations')
    return redirect('attendance:volunteer_dashboard')


@login_required
def volunteer_schedule(request):
    if not getattr(request.user, 'is_volunteer', lambda: False)() and not getattr(
        request.user, 'is_admin', lambda: False
    )():
        return HttpResponseForbidden()

    current_event = Event.get_current()
    from workshops.models import WorkshopSession
    from groups.models import Group
    from datetime import time

    sessions = (
        WorkshopSession.objects.select_related('workshop', 'group')
        .filter(group__event=current_event)
        .all()
    )
    
    period_definitions = []
    for value, label in WorkshopSession.PERIOD_CHOICES:
        # استبعاد فترات الانتقال والختام من جدول المتطوعين لتبسيط الواجهة
        if 'انتقال' in label or 'الخاتمة' in label or 'تسجيل' in label:
            continue
            
        start_str, end_str = value.split('-')
        
        def parse_time(t_str):
            h, m = map(int, t_str.split(':'))
            if h < 8: h += 12
            return time(h, m)
            
        period_definitions.append({
            'value': value,
            'label': label,
            'start': parse_time(start_str),
            'end': parse_time(end_str)
        })

    # بناء مصفوفة الجلسات لكل فترة
    schedule_data = []
    for period in period_definitions:
        period_sessions = []
        for s in sessions:
            # محاولة المطابقة عبر المفتاح أو التداخل الزمني
            if s.period == period['value'] or (s.start_time < period['end'] and s.end_time > period['start']):
                period_sessions.append(s)
        
        if period_sessions:
            schedule_data.append({
                'label': period['label'],
                'sessions': period_sessions
            })

    return render(
        request,
        'attendance/volunteer_schedule.html',
        {
            'schedule_data': schedule_data,
        },
    )


@login_required
def supervisor_award_points(request):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    
    event = Event.get_current()
    
    if request.method == 'POST':
        if event and not event.allow_group_points and not request.user.is_admin():
            messages.error(request, 'عذراً، إضافة النقاط مغلقة حالياً بقرار من الإدارة.')
            return redirect('attendance:award_points')
            
        student_id = request.POST.get('student_id')
        points = int(request.POST.get('points', 0))
        reason = request.POST.get('reason', 'مشاركة متميزة')
        
        student = get_object_or_404(Student, student_id=student_id)
        
        # التحقق من تسجيل الطالب في الفعالية الحالية
        is_registered = StudentRegistration.objects.filter(
            student=student,
            event=event,
            status=StudentRegistration.Status.APPROVED,
            removed_at__isnull=True,
        ).exists()
        
        if not is_registered:
            messages.error(request, 'عذراً، هذا الطالب غير مسجل في هذه الفعالية أو لم تتم الموافقة على طلبه بعد.')
            return redirect('attendance:award_points')
            
        if points != 0:
            student.points += points
            student.save(update_fields=['points'])
            
            # تحديث النقاط في إحصائيات الفعالية الحالية
            stats = StudentEventStats.objects.filter(student=student, event=event).first()
            if not stats:
                stats = StudentEventStats.objects.create(student=student, event=event)
            stats.points += points
            stats.save(update_fields=['points'])
            
            # إضافة نقاط للمجموعة فقط إذا كان مسموحاً بذلك في الإعدادات وللطلبة في الفعالية الحالية
            group_points_awarded = 0
            if student.group and student.group.event == event and event.allow_group_points:
                student.group.points += points
                student.group.save(update_fields=['points'])
                group_points_awarded = points
            
            AdminLog.objects.create(
                action=f'تم منح {points} نقطة للطالب {student.name} بواسطة {request.user.username}. السبب: {reason}',
                event=event
            )
            
            msg = f'تم إضافة {points} نقطة للطالب {student.name} بنجاح.'
            if student.group and student.group.event == event:
                if event.allow_group_points:
                    msg += f' وتم إضافة {points} نقطة لمجموعة {student.group.code}.'
                else:
                    msg += ' (لم يتم إضافة نقاط للمجموعة لأن الميزة مغلقة حالياً).'
            elif student.group:
                msg += ' (لم يتم إضافة نقاط للمجموعة لأن الطالب غير مسجل في مجموعة تابعة لهذه الفعالية).'
            
            messages.success(request, msg)
        
        return redirect('attendance:award_points')
    
    recent_awards = AdminLog.objects.filter(action__contains='نقطة للطالب').order_by('-created_at')[:10]
    return render(request, 'attendance/award_points.html', {
        'recent_awards': recent_awards,
        'allow_group_points': event.allow_group_points
    })


@login_required
def search_students(request):
    if not require_attendance_staff(request.user):
        return JsonResponse({'success': False, 'message': 'غير مسموح.'}, status=403)
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'success': True, 'students': []})
    
    event = Event.get_current()
    students = Student.objects.filter(
        name__icontains=query,
        registrations__event=event,
        registrations__status=StudentRegistration.Status.APPROVED,
        registrations__removed_at__isnull=True,
    ).select_related('group').distinct()[:15]
    
    results = []
    for s in students:
        results.append({
            'student_id': s.student_id,
            'name': s.name,
            'group_code': s.group.code if s.group and s.group.event == event else 'بدون مجموعة',
            'school': s.school or 'بدون مدرسة'
        })
    
    return JsonResponse({'success': True, 'students': results})
