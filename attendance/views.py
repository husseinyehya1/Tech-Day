from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone

from techday.utils import send_email_async, get_styled_email_html
from students.models import Student
from groups.models import Group
from users.models import User
from workshops.models import WorkshopSession, WorkshopFeedback
from dashboard.models import VolunteerNote, StudentViolation, AdminLog

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


def _register_attendance_for_session(student, session, status_value):
    now = timezone.localtime()
    workshop_title = ''
    points_awarded = 0
    is_session_already_registered = False
    
    # التحقق إذا كان الطالب سجل حضور من قبل في الفعالية (checked_in)
    is_event_already_checked_in = student.checked_in

    if session:
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            session=session,
            defaults={
                'status': status_value,
                'scanned_at': now,
            },
        )
        is_session_already_registered = not created
        
        if created:
            # إضافة نقاط للطالب وللمجموعة عند أول تسجيل حضور للجلسة
            if status_value == Attendance.Status.PRESENT:
                points_awarded = session.workshop.points_per_session
                student.points += points_awarded
                student.save(update_fields=['points'])
                if student.group:
                    student.group.points += points_awarded
                    student.group.save(update_fields=['points'])
        else:
            # إذا كانت موجودة بالفعل، نحدث الحالة فقط
            # لا نقوم بتحديث وقت المسح إذا كان موجوداً بالفعل للحفاظ على وقت أول دخول
            old_status = attendance.status
            attendance.status = status_value
            attendance.save()
            
            # تحديث النقاط إذا تغيرت الحالة من غائب/متأخر إلى حاضر
            if old_status != Attendance.Status.PRESENT and status_value == Attendance.Status.PRESENT:
                points_awarded = session.workshop.points_per_session
                student.points += points_awarded
                student.save(update_fields=['points'])
                if student.group:
                    student.group.points += points_awarded
                    student.group.save(update_fields=['points'])

        workshop_title = session.workshop.title

    if not is_event_already_checked_in:
        student.checked_in = True
        student.checked_in_at = now
        student.save(update_fields=['checked_in', 'checked_in_at'])
        _send_attendance_email(student, session, workshop_title, now)
    
    return workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered


@login_required
def scan_qr(request):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        status_value = request.POST.get('status') or Attendance.Status.PRESENT
        student = get_object_or_404(Student, student_id=student_id)
        now = timezone.localtime()
        session = None
        if student.group:
            session = (
                WorkshopSession.objects.filter(
                    group=student.group,
                    start_time__lte=now.time(),
                    end_time__gte=now.time(),
                )
                .select_related('workshop')
                .first()
            )
        workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered = _register_attendance_for_session(student, session, status_value)
        
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
                'message': message
            }
        )
    scan_url = reverse('attendance:scan_qr')
    return render(request, 'attendance/scan_qr.html', {'scan_url': scan_url})


@login_required
def scan_session_qr(request, session_id):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    session = get_object_or_404(
        WorkshopSession.objects.select_related('workshop', 'group'),
        pk=session_id,
    )
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        status_value = request.POST.get('status') or Attendance.Status.PRESENT
        student = get_object_or_404(Student, student_id=student_id)
        if not student.group or student.group_id != session.group_id:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'هذا الطالب ليس ضمن المجموعة المخصصة لهذه الجلسة.',
                }
            )
        workshop_title, is_event_already_checked_in, points_awarded, is_session_already_registered = _register_attendance_for_session(student, session, status_value)
        return JsonResponse(
            {
                'success': True,
                'is_already_checked_in': is_session_already_registered,
                'student': student.name,
                'group': student.group.code if student.group else '',
                'workshop': workshop_title,
                'points_awarded': points_awarded,
                'message': 'تم تسجيل الحضور لهذه الورشة مسبقاً' if is_session_already_registered else 'تم تسجيل الحضور بنجاح'
            }
        )
    scan_url = reverse('attendance:scan_session_qr', args=[session.id])
    return render(
        request,
        'attendance/scan_qr.html',
        {'scan_url': scan_url, 'session': session},
    )


@login_required
def volunteer_notes(request):
    if not getattr(request.user, 'is_volunteer', lambda: False)() and not getattr(
        request.user, 'is_admin', lambda: False
    )():
        return HttpResponseForbidden()
    if request.method == 'POST':
        text = (request.POST.get('note') or '').strip()
        if not text:
            messages.error(request, 'برجاء كتابة نص الملاحظة قبل الإرسال.')
        else:
            VolunteerNote.objects.create(author=request.user, text=text)
            messages.success(request, 'تم حفظ الملاحظة بنجاح.')
        return redirect('attendance:volunteer_notes')
    notes = VolunteerNote.objects.filter(author=request.user).order_by('-created_at')
    return render(
        request,
        'attendance/volunteer_notes.html',
        {
            'notes': notes,
        },
    )


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
    sessions = WorkshopSession.objects.select_related('workshop', 'group').all().order_by('period', 'group__code')
    periods = WorkshopSession.PERIOD_CHOICES
    groups = Group.objects.all()
    return render(
        request,
        'attendance/volunteer_schedule.html',
        {
            'sessions': sessions,
            'periods': periods,
            'groups': groups,
        },
    )


@login_required
def supervisor_award_points(request):
    if not require_attendance_staff(request.user):
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        points = int(request.POST.get('points', 0))
        reason = request.POST.get('reason', 'مشاركة متميزة')
        
        student = get_object_or_404(Student, student_id=student_id)
        
        if points != 0:
            student.points += points
            student.save(update_fields=['points'])
            if student.group:
                student.group.points += points
                student.group.save(update_fields=['points'])
            
            AdminLog.objects.create(
                action=f'تم منح {points} نقطة للطالب {student.name} بواسطة {request.user.username}. السبب: {reason}'
            )
            messages.success(request, f'تم إضافة {points} نقطة للطالب {student.name} بنجاح.')
        
        return redirect('attendance:award_points')
    
    recent_awards = AdminLog.objects.filter(action__contains='نقطة للطالب').order_by('-created_at')[:10]
    return render(request, 'attendance/award_points.html', {'recent_awards': recent_awards})


@login_required
def search_students(request):
    if not require_attendance_staff(request.user):
        return JsonResponse({'success': False, 'message': 'غير مسموح.'}, status=403)
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'success': True, 'students': []})
    
    students = Student.objects.filter(
        name__icontains=query
    ).select_related('group')[:15]
    
    results = []
    for s in students:
        results.append({
            'id': s.student_id,
            'name': s.name,
            'group': s.group.code if s.group else 'بدون مجموعة'
        })
    
    return JsonResponse({'success': True, 'students': results})
