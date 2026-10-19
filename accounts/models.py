from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.urls import reverse

from core.validators import validate_image_extension, validate_image_size


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        INSTRUCTOR = 'instructor', 'Instructor'
        ADMIN = 'admin', 'Administrator'

    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STUDENT, db_index=True)

    headline = models.CharField(max_length=120, blank=True,
                                help_text='Short professional headline, e.g. "Senior Data Engineer".')
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True,
                               validators=[validate_image_extension, validate_image_size])
    website = models.URLField(blank=True)

    # suspended users have is_active=False
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['username']

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p] or [self.username]
        return ''.join(p[0] for p in parts[:2]).upper()

    def get_absolute_url(self):
        return reverse('courses:instructor', args=[self.username])

    @property
    def pending_application(self):
        return self.instructor_applications.filter(status=InstructorApplication.Status.PENDING).first()


class InstructorApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='instructor_applications')
    headline = models.CharField(max_length=120)
    expertise = models.CharField(max_length=200, help_text='Subjects you want to teach.')
    experience = models.TextField(help_text='Teaching or professional experience.')
    sample_url = models.URLField(blank=True, help_text='Portfolio, sample lecture or LinkedIn.')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='applications_reviewed')
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=Q(status='pending'),
                                    name='one_pending_application_per_user'),
        ]

    def __str__(self):
        return f'Application by {self.user} ({self.get_status_display()})'
