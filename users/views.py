from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, 'is_admin') and user.is_admin():
                return redirect('dashboard:admin_dashboard')
            if hasattr(user, 'role') and user.role == 'supervisor':
                return redirect('attendance:scan_qr')
            if hasattr(user, 'student_profile'):
                return redirect('students:detail', pk=user.student_profile.pk)
            return redirect('dashboard:admin_dashboard')
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    return render(request, 'users/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect(reverse('users:login'))
