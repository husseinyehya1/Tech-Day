from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404

class EnsurePhoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # التحقق مما إذا كان المستخدم طالباً
            if hasattr(request.user, 'role') and request.user.role == 'student':
                # استثناء مسار تحديث الهاتف ومسار تسجيل الخروج باستخدام resolve لضمان الدقة
                try:
                    current_url_name = resolve(request.path_info).view_name
                except Resolver404:
                    current_url_name = None

                exempt_view_names = [
                    'students:update_phone',
                    'users:logout',
                ]
                
                if current_url_name not in exempt_view_names:
                    # التحقق من وجود رقم الهاتف في البروفايل
                    student_profile = getattr(request.user, 'student_profile', None)
                    if student_profile and not student_profile.phone_number:
                        return redirect('students:update_phone')

        response = self.get_response(request)
        return response
