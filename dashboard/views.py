from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Max, Q
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from attendance.models import Attendance
from groups.models import Group
from students.models import Student
from users.models import User
from workshops.models import Workshop, WorkshopSession

from .models import AdminLog, Notification


def require_admin(user):
    return user.is_authenticated and hasattr(user, 'is_admin') and user.is_admin()


@login_required
def admin_dashboard(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    now = timezone.localtime()
    total_students = Student.objects.count()
    total_present = Student.objects.filter(checked_in=True).count()
    workshops = Workshop.objects.all()
    groups = Group.objects.all()
    active_workshops = workshops.filter(status='active').count()
    latest_notification = Notification.objects.filter(is_active=True).first()
    recent_logs = AdminLog.objects.all()[:5]
    event_status = 'جارية'
    context = {
        'now': now,
        'total_students': total_students,
        'total_present': total_present,
        'workshops': workshops,
        'groups': groups,
        'active_workshops': active_workshops,
        'latest_notification': latest_notification,
        'recent_logs': recent_logs,
        'event_status': event_status,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def admin_students_list(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    students_qs = Student.objects.select_related('group').all()
    q = request.GET.get('q') or ''
    group_id = request.GET.get('group') or ''
    if q:
        students_qs = students_qs.filter(Q(name__icontains=q) | Q(student_id__icontains=q))
    if group_id:
        students_qs = students_qs.filter(group_id=group_id)
    students = list(students_qs)
    for student in students:
        student.current_status = 'present' if student.checked_in else None
    groups = Group.objects.all()
    return render(request, 'dashboard/admin_students_list.html', {'students': students, 'groups': groups})


@login_required
def admin_student_create(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    groups = Group.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name') or ''
        student_id = request.POST.get('student_id') or ''
        group_id = request.POST.get('group') or ''
        school = request.POST.get('school') or ''
        education_admin = request.POST.get('education_admin') or ''
        email = request.POST.get('email') or ''
        group = Group.objects.filter(id=group_id).first() if group_id else None
        user = None
        password_plain = None
        if student_id:
            username = f'student_{student_id}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'role': User.Roles.STUDENT, 'email': email},
            )
            if created:
                from django.utils.crypto import get_random_string

                password_plain = get_random_string(10)
                user.set_password(password_plain)
                user.save()
        Student.objects.create(
            name=name,
            student_id=student_id,
            group=group,
            school=school,
            education_admin=education_admin,
            email=email,
            user=user,
        )
        AdminLog.objects.create(action=f'تم إضافة الطالب {name}')
        if password_plain and email:
            subject = 'بيانات حسابك في نظام Tech Day – EduTech Egypt'
            text_body = (
                f'مرحبًا {name},\n\n'
                f'يسعدنا مشاركتك في فعالية Tech Day – الفريق التقني بالقليوبية.\n\n'
                f'تم إنشاء حساب لك على نظام متابعة الفعالية، ويمكنك استخدام البيانات التالية لتسجيل الدخول:\n\n'
                f'اسم المستخدم: {username}\n'
                f'كلمة المرور: {password_plain}\n\n'
                f'رابط تسجيل الدخول: https://edutech-egy.com/techday/login\n\n'
                f'ننصحك بتغيير كلمة المرور بعد أول تسجيل دخول للحفاظ على خصوصية حسابك.\n\n'
                f'في حال واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.\n\n'
                f'تحياتنا،\n'
                f'EduTech Egypt System'
            )
            html_body = f"""
<!DOCTYPE html>
<html lang="ar">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>{subject}</title>
  </head>
  <body style="margin:0;padding:0;background-color:#0f172a;direction:rtl;text-align:right;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background-color:#020617;border-radius:16px;border:1px solid #1e293b;">
            <tr>
              <td style="padding:24px 24px 16px 24px;border-bottom:1px solid #1e293b;">
                <h1 style="margin:0;font-size:20px;color:#e2e8f0;">مرحبًا {name}</h1>
                <p style="margin:8px 0 0;font-size:13px;color:#94a3b8;">
                  يسعدنا مشاركتك في فعالية Tech Day – الفريق التقني بالقليوبية.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px 8px 24px;">
                <p style="margin:0 0 12px;font-size:13px;color:#cbd5f5;">
                  تم إنشاء حساب لك على نظام متابعة الفعالية. استخدم البيانات التالية لتسجيل الدخول:
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;color:#e2e8f0;">
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">اسم المستخدم</td>
                    <td style="padding:8px 0;font-family:monospace;color:#22d3ee;">{username}</td>
                  </tr>
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">كلمة المرور</td>
                    <td style="padding:8px 0;font-family:monospace;color:#f97316;">{password_plain}</td>
                  </tr>
                </table>
                <p style="margin:12px 0 0;font-size:12px;color:#f97316;">
                  ننصحك بتغيير كلمة المرور بعد أول تسجيل دخول للحفاظ على خصوصية حسابك.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 24px 24px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td>
                      <a href="https://edutech-egy.com/techday/login"
                         style="display:inline-block;padding:10px 18px;border-radius:999px;background:linear-gradient(90deg,#06b6d4,#6366f1);color:#020617;font-size:13px;font-weight:600;text-decoration:none;">
                        تسجيل الدخول الآن
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;">
                  إذا واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.
                </p>
                <p style="margin:4px 0 0;font-size:12px;color:#64748b;">
                  تحياتنا،<br>
                  EduTech Egypt System
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
            try:
                message = EmailMultiAlternatives(
                    subject,
                    text_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                message.attach_alternative(html_body, 'text/html')
                message.send(fail_silently=False)
                messages.success(request, 'تم إضافة الطالب، وتم إرسال رسالة دخول احترافية إلى بريده الإلكتروني.')
            except Exception as e:
                messages.error(request, f'تم إضافة الطالب، لكن تعذّر إرسال البريد الإلكتروني: {e}')
        else:
            messages.success(request, 'تم إضافة الطالب بنجاح.')
        return redirect('dashboard:admin_students_list')
    return render(request, 'dashboard/admin_student_form.html', {'groups': groups})


@login_required
def admin_student_update(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    student = get_object_or_404(Student, pk=pk)
    groups = Group.objects.all()
    if request.method == 'POST':
        student.name = request.POST.get('name') or student.name
        student.student_id = request.POST.get('student_id') or student.student_id
        group_id = request.POST.get('group') or ''
        student.school = request.POST.get('school') or ''
        student.education_admin = request.POST.get('education_admin') or student.education_admin
        student.email = request.POST.get('email') or student.email
        group = Group.objects.filter(id=group_id).first() if group_id else None
        student.group = group
        student.save()
        AdminLog.objects.create(action=f'تم تحديث بيانات الطالب {student.name}')
        messages.success(request, 'تم تحديث بيانات الطالب')
        return redirect('dashboard:admin_students_list')
    return render(request, 'dashboard/admin_student_form.html', {'student': student, 'groups': groups})


@login_required
def admin_student_send_credentials(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    student = get_object_or_404(Student, pk=pk)
    if request.method != 'POST':
        return redirect('dashboard:admin_students_list')
    email = student.email or ''
    if not email:
        messages.error(request, 'لا يمكن إرسال بيانات الدخول لأن البريد الإلكتروني غير مسجل للطالب.')
        return redirect('dashboard:admin_students_list')
    user = student.user
    if not user and student.student_id:
        username = f'student_{student.student_id}'
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'role': User.Roles.STUDENT, 'email': email},
        )
        if created:
            student.user = user
            student.save()
    if not user:
        messages.error(request, 'لا يمكن إرسال بيانات الدخول لأن حساب المستخدم غير متوفر.')
        return redirect('dashboard:admin_students_list')
    from django.utils.crypto import get_random_string

    password_plain = get_random_string(10)
    user.set_password(password_plain)
    user.email = email
    user.save()
    name = student.name
    username = user.username
    subject = 'تحديث بيانات حسابك في نظام Tech Day – EduTech Egypt'
    text_body = (
        f'مرحبًا {name},\n\n'
        f'تم تحديث بيانات الدخول الخاصة بحسابك على نظام متابعة فعالية Tech Day – الفريق التقني بالقليوبية.\n\n'
        f'يمكنك استخدام البيانات التالية لتسجيل الدخول:\n\n'
        f'اسم المستخدم: {username}\n'
        f'كلمة المرور الجديدة: {password_plain}\n\n'
        f'رابط تسجيل الدخول: https://edutech-egy.com/techday/login\n\n'
        f'ننصحك بتغيير كلمة المرور بعد تسجيل الدخول للحفاظ على خصوصية حسابك.\n\n'
        f'في حال واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.\n\n'
        f'تحياتنا،\n'
        f'EduTech Egypt System'
    )
    html_body = f"""
<!DOCTYPE html>
<html lang="ar">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>{subject}</title>
  </head>
  <body style="margin:0;padding:0;background-color:#0f172a;direction:rtl;text-align:right;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background-color:#020617;border-radius:16px;border:1px solid #1e293b;">
            <tr>
              <td style="padding:24px 24px 16px 24px;border-bottom:1px solid #1e293b;">
                <h1 style="margin:0;font-size:20px;color:#e2e8f0;">مرحبًا {name}</h1>
                <p style="margin:8px 0 0;font-size:13px;color:#94a3b8;">
                  تم تحديث بيانات الدخول الخاصة بحسابك على نظام متابعة فعالية Tech Day – الفريق التقني بالقليوبية.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px 8px 24px;">
                <p style="margin:0 0 12px;font-size:13px;color:#cbd5f5;">
                  يمكنك استخدام البيانات التالية لتسجيل الدخول إلى حسابك:
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;color:#e2e8f0;">
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">اسم المستخدم</td>
                    <td style="padding:8px 0;font-family:monospace;color:#22d3ee;">{username}</td>
                  </tr>
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">كلمة المرور الجديدة</td>
                    <td style="padding:8px 0;font-family:monospace;color:#f97316;">{password_plain}</td>
                  </tr>
                </table>
                <p style="margin:12px 0 0;font-size:12px;color:#f97316;">
                  ننصحك بتغيير كلمة المرور بعد تسجيل الدخول للحفاظ على خصوصية حسابك.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 24px 24px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td>
                      <a href="https://edutech-egy.com/techday/login"
                         style="display:inline-block;padding:10px 18px;border-radius:999px;background:linear-gradient(90deg,#06b6d4,#6366f1);color:#020617;font-size:13px;font-weight:600;text-decoration:none;">
                        تسجيل الدخول الآن
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;">
                  إذا واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.
                </p>
                <p style="margin:4px 0 0;font-size:12px;color:#64748b;">
                  تحياتنا،<br>
                  EduTech Egypt System
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    try:
        message = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)
        messages.success(request, 'تم إرسال بيانات الدخول الجديدة إلى بريد الطالب الإلكتروني.')
    except Exception as e:
        messages.error(request, f'تم تحديث كلمة مرور الطالب، لكن تعذّر إرسال البريد الإلكتروني: {e}')
    return redirect('dashboard:admin_students_list')


@login_required
def admin_student_delete(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        AdminLog.objects.create(action=f'تم حذف الطالب {student.name}')
        messages.success(request, 'تم حذف الطالب')
        return redirect('dashboard:admin_students_list')
    return render(request, 'dashboard/admin_student_delete_confirm.html', {'student': student})


@login_required
def admin_student_transfer(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    student = get_object_or_404(Student, pk=pk)
    groups = Group.objects.all()
    if request.method == 'POST':
        group_id = request.POST.get('group') or ''
        group = Group.objects.filter(id=group_id).first() if group_id else None
        old_group = student.group
        student.group = group
        student.save()
        AdminLog.objects.create(action=f'تم نقل الطالب {student.name} من مجموعة {old_group} إلى {group}')
        messages.success(request, 'تم نقل الطالب بنجاح')
        return redirect('dashboard:admin_students_list')
    return render(request, 'dashboard/admin_student_transfer.html', {'student': student, 'groups': groups})


@login_required
def admin_groups(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    groups = Group.objects.all()
    return render(request, 'dashboard/admin_groups.html', {'groups': groups})


@login_required
def admin_group_create(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        name = request.POST.get('name') or ''
        code = request.POST.get('code') or ''
        color = request.POST.get('color') or ''
        max_students = int(request.POST.get('max_students') or 0) or 25
        group = Group.objects.create(name=name, code=code, color=color, max_students=max_students)
        AdminLog.objects.create(action=f'تم إنشاء المجموعة {group}')
        messages.success(request, 'تم إنشاء المجموعة بنجاح')
        return redirect('dashboard:admin_groups')
    return render(request, 'dashboard/admin_group_form.html')


@login_required
def admin_group_update(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        group.name = request.POST.get('name') or group.name
        group.code = request.POST.get('code') or group.code
        group.color = request.POST.get('color') or group.color
        group.max_students = int(request.POST.get('max_students') or group.max_students)
        group.save()
        AdminLog.objects.create(action=f'تم تعديل المجموعة {group}')
        messages.success(request, 'تم تعديل المجموعة')
        return redirect('dashboard:admin_groups')
    return render(request, 'dashboard/admin_group_form.html', {'group': group})


@login_required
def admin_groups_redistribute(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    groups = list(Group.objects.all())
    students = list(Student.objects.all())
    if groups and students:
        index = 0
        for student in students:
            student.group = groups[index % len(groups)]
            student.save()
            index += 1
        AdminLog.objects.create(action='تم إعادة توزيع الطلاب على المجموعات')
        messages.success(request, 'تم إعادة توزيع الطلاب على المجموعات')
    return redirect('dashboard:admin_groups')


@login_required
def admin_workshops(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    workshops = Workshop.objects.select_related('supervisor').all()
    return render(request, 'dashboard/admin_workshops.html', {'workshops': workshops})


@login_required
def admin_workshop_create(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    supervisors = User.objects.filter(role=User.Roles.SUPERVISOR)
    if request.method == 'POST':
        title = request.POST.get('title') or ''
        room = request.POST.get('room') or ''
        supervisor_id = request.POST.get('supervisor') or ''
        supervisor = supervisors.filter(id=supervisor_id).first() if supervisor_id else None
        status = request.POST.get('status') or 'upcoming'
        workshop = Workshop.objects.create(
            title=title,
            room=room,
            supervisor=supervisor,
            status=status,
        )
        AdminLog.objects.create(action=f'تم إنشاء الورشة {workshop.title}')
        messages.success(request, 'تم إنشاء الورشة بنجاح')
        return redirect('dashboard:admin_workshops')
    return render(
        request,
        'dashboard/admin_workshop_form.html',
        {'supervisors': supervisors},
    )


@login_required
def admin_workshop_update(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    workshop = get_object_or_404(Workshop, pk=pk)
    supervisors = User.objects.filter(role=User.Roles.SUPERVISOR)
    if request.method == 'POST':
        workshop.title = request.POST.get('title') or workshop.title
        workshop.room = request.POST.get('room') or workshop.room
        supervisor_id = request.POST.get('supervisor') or ''
        workshop.supervisor = supervisors.filter(id=supervisor_id).first() if supervisor_id else None
        workshop.status = request.POST.get('status') or workshop.status
        workshop.save()
        AdminLog.objects.create(action=f'تم تعديل الورشة {workshop.title}')
        messages.success(request, 'تم تعديل الورشة')
        return redirect('dashboard:admin_workshops')
    return render(
        request,
        'dashboard/admin_workshop_form.html',
        {'workshop': workshop, 'supervisors': supervisors},
    )


@login_required
def admin_workshop_toggle_status(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    workshop = get_object_or_404(Workshop, pk=pk)
    if workshop.status == 'active':
        workshop.status = 'finished'
    else:
        workshop.status = 'active'
    workshop.save()
    AdminLog.objects.create(action=f'تم تغيير حالة الورشة {workshop.title} إلى {workshop.get_status_display()}')
    messages.success(request, 'تم تحديث حالة الورشة')
    return redirect('dashboard:admin_workshops')


@login_required
def admin_supervisors(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    supervisors = User.objects.filter(role=User.Roles.SUPERVISOR).annotate(
        workshop_count=Count('supervised_workshops')
    )
    return render(request, 'dashboard/admin_supervisors.html', {'supervisors': supervisors})


@login_required
def admin_supervisor_create(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        first_name = request.POST.get('first_name') or ''
        last_name = request.POST.get('last_name') or ''
        email = request.POST.get('email') or ''
        username_base = ''
        if email and '@' in email:
            username_base = email.split('@', 1)[0]
        if not username_base:
            username_base = 'supervisor'
        username = username_base
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f'{username_base}{suffix}'
        from django.utils.crypto import get_random_string

        password_plain = get_random_string(10)
        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=User.Roles.SUPERVISOR,
        )
        user.set_password(password_plain)
        user.save()
        AdminLog.objects.create(action=f'تم إنشاء مشرف جديد: {user.get_full_name() or user.username}')
        if email:
            subject = 'بيانات حسابك كمشرف ورشة في نظام Tech Day – EduTech Egypt'
            name = user.get_full_name() or username
            text_body = (
                f'مرحبًا {name},\n\n'
                f'تم إنشاء حساب لك كمشرف ورشة على نظام Tech Day – الفريق التقني بالقليوبية.\n\n'
                f'يمكنك استخدام البيانات التالية لتسجيل الدخول:\n\n'
                f'اسم المستخدم: {username}\n'
                f'كلمة المرور: {password_plain}\n\n'
                f'رابط تسجيل الدخول: https://edutech-egy.com/techday/login\n\n'
                f'ننصحك بتغيير كلمة المرور بعد أول تسجيل دخول للحفاظ على خصوصية حسابك.\n\n'
                f'في حال واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.\n\n'
                f'تحياتنا،\n'
                f'EduTech Egypt System'
            )
            html_body = f"""
<!DOCTYPE html>
<html lang="ar">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>{subject}</title>
  </head>
  <body style="margin:0;padding:0;background-color:#0f172a;direction:rtl;text-align:right;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background-color:#020617;border-radius:16px;border:1px solid #1e293b;">
            <tr>
              <td style="padding:24px 24px 16px 24px;border-bottom:1px solid #1e293b;">
                <h1 style="margin:0;font-size:20px;color:#e2e8f0;">مرحبًا {name}</h1>
                <p style="margin:8px 0 0;font-size:13px;color:#94a3b8;">
                  تم إنشاء حساب لك كمشرف ورشة على نظام متابعة فعالية Tech Day – الفريق التقني بالقليوبية.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px 8px 24px;">
                <p style="margin:0 0 12px;font-size:13px;color:#cbd5f5;">
                  يمكنك استخدام البيانات التالية لتسجيل الدخول إلى حسابك:
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;color:#e2e8f0%;">
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">اسم المستخدم</td>
                    <td style="padding:8px 0;font-family:monospace;color:#22d3ee;">{username}</td>
                  </tr>
                  <tr>
                    <td style="padding:8px 0;width:120px;color:#94a3b8;">كلمة المرور</td>
                    <td style="padding:8px 0;font-family:monospace;color:#f97316;">{password_plain}</td>
                  </tr>
                </table>
                <p style="margin:12px 0 0;font-size:12px;color:#f97316;">
                  ننصحك بتغيير كلمة المرور بعد أول تسجيل دخول للحفاظ على خصوصية حسابك.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 24px 24px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td>
                      <a href="https://edutech-egy.com/techday/login"
                         style="display:inline-block;padding:10px 18px;border-radius:999px;background:linear-gradient(90deg,#06b6d4,#6366f1);color:#020617;font-size:13px;font-weight:600;text-decoration:none;">
                        تسجيل الدخول الآن
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;">
                  إذا واجهت أي مشكلة في تسجيل الدخول يمكنك التواصل مع فريق الدعم.
                </p>
                <p style="margin:4px 0 0;font-size:12px;color:#64748b;">
                  تحياتنا،<br>
                  EduTech Egypt System
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
            try:
                message = EmailMultiAlternatives(
                    subject,
                    text_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                message.attach_alternative(html_body, 'text/html')
                message.send(fail_silently=False)
                messages.success(
                    request,
                    'تم إنشاء المشرف بنجاح، وتم إرسال بيانات الدخول إلى بريده الإلكتروني.',
                )
            except Exception as e:
                messages.error(
                    request,
                    f'تم إنشاء المشرف، لكن تعذّر إرسال البريد الإلكتروني: {e}',
                )
        else:
            messages.success(request, 'تم إنشاء المشرف بنجاح.')
        return redirect('dashboard:admin_supervisors')
    return render(request, 'dashboard/admin_supervisor_form.html')


@login_required
def admin_supervisor_update(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    supervisor = get_object_or_404(User, pk=pk, role=User.Roles.SUPERVISOR)
    if request.method == 'POST':
        supervisor.first_name = request.POST.get('first_name') or supervisor.first_name
        supervisor.last_name = request.POST.get('last_name') or supervisor.last_name
        supervisor.email = request.POST.get('email') or supervisor.email
        supervisor.save()
        AdminLog.objects.create(action=f'تم تعديل بيانات المشرف {supervisor.get_full_name() or supervisor.username}')
        messages.success(request, 'تم تعديل بيانات المشرف')
        return redirect('dashboard:admin_supervisors')
    return render(request, 'dashboard/admin_supervisor_form.html', {'supervisor': supervisor})


@login_required
def admin_schedule(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    sessions = WorkshopSession.objects.select_related('workshop', 'group').all()
    periods = WorkshopSession.PERIOD_CHOICES
    groups = Group.objects.all()
    return render(
        request,
        'dashboard/admin_schedule.html',
        {'sessions': sessions, 'periods': periods, 'groups': groups},
    )


@login_required
def admin_session_update(request, pk):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    session = get_object_or_404(WorkshopSession, pk=pk)
    workshops = Workshop.objects.all()
    groups = Group.objects.all()
    if request.method == 'POST':
        workshop_id = request.POST.get('workshop') or ''
        group_id = request.POST.get('group') or ''
        period = request.POST.get('period') or session.period
        start_time = request.POST.get('start_time') or session.start_time
        end_time = request.POST.get('end_time') or session.end_time
        session.workshop = workshops.filter(id=workshop_id).first() if workshop_id else session.workshop
        session.group = groups.filter(id=group_id).first() if group_id else session.group
        session.period = period
        session.start_time = start_time
        session.end_time = end_time
        session.save()
        AdminLog.objects.create(action='تم تعديل جلسة في الجدول الزمني')
        messages.success(request, 'تم تعديل الجلسة')
        return redirect('dashboard:admin_schedule')
    return render(
        request,
        'dashboard/admin_session_form.html',
        {'session': session, 'workshops': workshops, 'groups': groups},
    )


@login_required
def admin_notifications(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    notifications = Notification.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title') or ''
        body = request.POST.get('body') or ''
        target = request.POST.get('target') or Notification.Target.ALL
        group_id = request.POST.get('group') or ''
        group = Group.objects.filter(id=group_id).first() if group_id else None
        notification = Notification.objects.create(
            title=title,
            body=body,
            target=target,
            group=group,
        )
        AdminLog.objects.create(action=f'تم إرسال تنبيه: {notification.title}')
        messages.success(request, 'تم إرسال التنبيه')
        return redirect('dashboard:admin_notifications')
    groups = Group.objects.all()
    return render(
        request,
        'dashboard/admin_notifications.html',
        {'notifications': notifications, 'groups': groups},
    )


@login_required
def admin_reports(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    total_students = Student.objects.count()
    total_attendance = Student.objects.filter(checked_in=True).count()
    by_group = (
        Group.objects.annotate(
            present_count=Count(
                'students',
                filter=Q(students__checked_in=True),
                distinct=True,
            )
        )
        .values('name', 'code', 'present_count')
        .order_by('-present_count')
    )
    by_workshop = (
        Workshop.objects.annotate(
            present_count=Count(
                'sessions__attendance_records',
                filter=Q(sessions__attendance_records__status=Attendance.Status.PRESENT),
            )
        )
        .values('title', 'present_count')
        .order_by('-present_count')
    )
    most_attended = by_workshop[0] if by_workshop else None
    context = {
        'total_students': total_students,
        'total_attendance': total_attendance,
        'by_group': by_group,
        'by_workshop': by_workshop,
        'most_attended': most_attended,
    }
    return render(request, 'dashboard/admin_reports.html', context)


@login_required
def admin_reports_export_csv(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="techday_report.csv"'
    lines = ['اسم المجموعة,الكود,عدد الحضور\n']
    by_group = (
        Group.objects.annotate(
            present_count=Count(
                'students__attendance_records',
                filter=Q(students__attendance_records__status=Attendance.Status.PRESENT),
            )
        )
        .values('name', 'code', 'present_count')
        .order_by('code')
    )
    for item in by_group:
        lines.append(f"{item['name']},{item['code']},{item['present_count']}\n")
    response.write(''.join(lines))
    return response


@login_required
def admin_public_screen(request):
    if not require_admin(request.user):
        return HttpResponseForbidden()
    screen_url = request.build_absolute_uri('/')
    latest_notification = Notification.objects.filter(is_active=True).first()
    return render(
        request,
        'dashboard/admin_public_screen.html',
        {'screen_url': screen_url, 'latest_notification': latest_notification},
    )
