from django.contrib import messages
from django.shortcuts import redirect

from .services import CourseLocked


class CourseLockedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, CourseLocked):
            messages.error(request, str(exception))
            return redirect('studio:course', exception.course.pk)
        return None
