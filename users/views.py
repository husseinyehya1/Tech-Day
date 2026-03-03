from django.contrib.auth import authenticate, login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from students.models import Student


def login_view(request):
    error = None
    if request.method == 'POST':
        identifier = (request.POST.get('username') or '').strip()
        password = request.POST.get('password')
        user = None
        if identifier and password:
            user = authenticate(request, username=identifier, password=password)
            if user is None:
                User = get_user_model()
                try:
                    account = User.objects.get(email__iexact=identifier)
                except User.DoesNotExist:
                    account = None
                except User.MultipleObjectsReturned:
                    account = None
                if account is None:
                    student = (
                        Student.objects.select_related('user')
                        .filter(email__iexact=identifier, user__isnull=False)
                        .first()
                    )
                    if student and student.user:
                        account = student.user
                if account is not None:
                    user = authenticate(request, username=account.username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, 'is_admin') and user.is_admin():
                return redirect('dashboard:admin_dashboard')
            if hasattr(user, 'role') and user.role == 'supervisor':
                return redirect('workshops:list')
            if hasattr(user, 'role') and user.role == 'volunteer':
                return redirect('attendance:volunteer_dashboard')
            if hasattr(user, 'student_profile'):
                return redirect('students:detail', pk=user.student_profile.pk)
            return redirect('dashboard:admin_dashboard')
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    return render(request, 'users/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect(reverse('users:login'))


@login_required
def change_password(request):
    error = None
    success = None
    if request.method == 'POST':
        old_password = request.POST.get('old_password') or ''
        new_password1 = request.POST.get('new_password1') or ''
        new_password2 = request.POST.get('new_password2') or ''
        if not request.user.check_password(old_password):
            error = 'كلمة المرور الحالية غير صحيحة.'
        elif not new_password1 or len(new_password1) < 8:
            error = 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل.'
        elif new_password1 != new_password2:
            error = 'تأكيد كلمة المرور لا يطابق الكلمة الجديدة.'
        else:
            user = request.user
            user.set_password(new_password1)
            user.save()
            update_session_auth_hash(request, user)
            success = 'تم تحديث كلمة المرور بنجاح.'
    return render(request, 'users/change_password.html', {'error': error, 'success': success})
