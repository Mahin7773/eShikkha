from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*checks, message=None):
    """Usage: @role_required('is_student', 'is_instructor')"""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if any(getattr(user, check, False) for check in checks):
                return view(request, *args, **kwargs)
            if message:
                messages.error(request, message)
                return redirect('core:home')
            raise PermissionDenied
        return wrapper
    return decorator


student_required = role_required(
    'is_student', message='This area is for student accounts.')
instructor_required = role_required(
    'is_instructor', message='The instructor studio is available to approved instructors only.')
admin_required = role_required('is_platform_admin')
