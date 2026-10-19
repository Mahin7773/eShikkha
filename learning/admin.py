from django.contrib import admin

from .models import Certificate, Enrollment, LessonCompletion


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'source', 'status', 'progress_percent', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'source')


admin.site.register([Certificate, LessonCompletion])
