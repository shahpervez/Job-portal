from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this page.")
                return redirect('login')

            # Check role on custom user model or profile
            user_role = getattr(request.user, 'role', None)
            if not user_role and hasattr(request.user, 'profile'):
                user_role = getattr(request.user.profile, 'role', None)

            # Superusers and staff have administrative access
            if request.user.is_superuser or (user_role in allowed_roles) or ('admin' in allowed_roles and request.user.is_staff):
                return view_func(request, *args, **kwargs)

            messages.error(request, "You do not have permission to access this page.")
            return redirect('job_list')  # Redirects to home/job listing if unauthorized

        return _wrapped_view
    return decorator