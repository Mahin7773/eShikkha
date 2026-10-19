from django.conf import settings
from django.db import models
from django.urls import reverse


class Enrollment(models.Model):
    class Source(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        FREE = 'free', 'Free enrolment'
        ADMIN = 'admin', 'Granted by administrator'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        REFUNDED = 'refunded', 'Refunded'
        REVOKED = 'revoked', 'Revoked'

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('courses.Course', on_delete=models.PROTECT, related_name='enrollments')
    order = models.ForeignKey('commerce.Order', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='enrollments')
    source = models.CharField(max_length=10, choices=Source.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    # cached value, updated by services.recalculate_progress()
    progress_percent = models.PositiveSmallIntegerField(default=0)
    last_lesson = models.ForeignKey('courses.Lesson', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_enrollment_per_student_course'),
        ]
        indexes = [models.Index(fields=['student', 'status']), models.Index(fields=['course', 'status'])]

    def __str__(self):
        return f'{self.student} → {self.course}'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_completed(self):
        return self.completed_at is not None

    def get_resume_url(self):
        return reverse('learning:resume', args=[self.course.slug])


class LessonCompletion(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='completions')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['enrollment', 'lesson'], name='unique_lesson_completion'),
        ]

    def __str__(self):
        return f'{self.enrollment.student} completed {self.lesson}'


class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.PROTECT, related_name='certificate')
    certificate_number = models.CharField(max_length=24, unique=True)
    # copied at issue time so later renames don't change old certificates
    student_name = models.CharField(max_length=150)
    course_title = models.CharField(max_length=120)
    instructor_name = models.CharField(max_length=150)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return self.certificate_number

    def get_absolute_url(self):
        return reverse('learning:verify_certificate', args=[self.certificate_number])
