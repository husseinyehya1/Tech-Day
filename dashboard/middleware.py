from django.shortcuts import redirect, render
from django.urls import reverse
from .models import Event

class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Always allow access to the Django admin
        if request.path.startswith('/admin') or request.path_info.startswith('/admin'):
            return self.get_response(request)

        event = Event.get_current()
        
        # Check if maintenance mode is on
        if event and event.is_maintenance_mode:
            # Allow admins to access the dashboard and login
            is_admin = False
            if request.user.is_authenticated:
                if hasattr(request.user, 'role'):
                    is_admin = request.user.role == 'admin' or request.user.is_superuser
                else:
                    is_admin = request.user.is_superuser

            # Exempt maintenance page, login, logout, and admin (django admin)
            exempt_url_names = [
                'dashboard:maintenance_page',
                'users:login',
                'users:logout',
                'token_obtain_pair', # API Login
            ]
            
            # Resolve the current path to its name to compare safely
            from django.urls import resolve
            try:
                resolver_match = resolve(request.path_info)
                # Check all namespaces if nested
                namespaces = resolver_match.namespaces
                url_name = resolver_match.url_name
                
                is_exempt = False
                for ns in namespaces:
                    if f"{ns}:{url_name}" in exempt_url_names:
                        is_exempt = True
                        break
                # Also check without namespace if needed (though our list has them)
                if not is_exempt and url_name in exempt_url_names:
                    is_exempt = True
            except:
                is_exempt = False

            is_api = request.path.startswith('/api') or request.path_info.startswith('/api')
            
            # Check if it's the API login or status endpoint by path as a fallback
            is_api_exempt = '/api/auth/login' in request.path or '/api/events/current' in request.path or '/api/auth/login' in request.path_info or '/api/events/current' in request.path_info
            
            # If not admin, not on an exempt page, and not API, show maintenance template directly
            if not is_admin and not is_exempt and not is_api and not is_api_exempt:
                return render(request, 'dashboard/maintenance.html', {
                    'facebook_url': event.maintenance_facebook_url
                }, status=503)

        response = self.get_response(request)
        return response
