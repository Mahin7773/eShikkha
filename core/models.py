from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class PlatformSettings(models.Model):
    """Single row (pk=1) with site-wide options."""

    site_name = models.CharField(max_length=80, default='eShikkha')
    tagline = models.CharField(max_length=160, default='Learn practical skills from expert instructors')
    support_email = models.EmailField(default='support@eshikkha.local')

    require_instructor_approval = models.BooleanField(
        default=True, help_text='New instructors must be approved by an administrator.')
    require_course_approval = models.BooleanField(
        default=True, help_text='Courses must be reviewed by an administrator before publication.')
    reapprove_published_edits = models.BooleanField(
        default=False,
        help_text='Editing the details of a published course sends it back for review. '
                  'Enrolled students keep access while it is reviewed.')
    allow_discounts = models.BooleanField(default=True, help_text='Instructors may set discounted prices.')
    max_course_price = models.DecimalField(max_digits=8, decimal_places=2, default=500)
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=30,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Share of each simulated sale retained by the platform.')
    review_min_progress = models.PositiveSmallIntegerField(
        default=10, validators=[MaxValueValidator(100)],
        help_text='Minimum course progress (%) before a student may leave a review.')

    # Certificate template
    certificate_title = models.CharField(max_length=80, default='Certificate of Completion')
    certificate_signatory_name = models.CharField(max_length=80, default='Academic Board')
    certificate_signatory_title = models.CharField(max_length=80, default='eShikkha Learning Platform')
    certificate_accent_color = models.CharField(
        max_length=7, default='#0e6655',
        validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Use a hex colour such as #0e6655.')])
    certificate_show_qr = models.BooleanField(default=True, help_text='Print a verification QR code.')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'platform settings'
        verbose_name_plural = 'platform settings'

    def __str__(self):
        return f'{self.site_name} settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = 'all', 'Everyone'
        STUDENTS = 'students', 'Students'
        INSTRUCTORS = 'instructors', 'Instructors'

    title = models.CharField(max_length=140)
    body = models.TextField()
    audience = models.CharField(max_length=12, choices=Audience.choices, default=Audience.ALL)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='audit_entries')
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_repr = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['target_type', 'target_id'])]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target_repr}'


class Report(models.Model):
    class TargetType(models.TextChoices):
        COURSE = 'course', 'Course'
        REVIEW = 'review', 'Review'
        USER = 'user', 'User'

    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam or advertising'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate or offensive'
        MISLEADING = 'misleading', 'Misleading content'
        COPYRIGHT = 'copyright', 'Copyright infringement'
        HARASSMENT = 'harassment', 'Harassment'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved (action taken)'
        DISMISSED = 'dismissed', 'Dismissed'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='reports_filed')
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    course = models.ForeignKey('courses.Course', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='reports')
    review = models.ForeignKey('courses.Review', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='reports')
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.CASCADE, related_name='reports_received')
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='reports_resolved')
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(target_type='course', course__isnull=False)
                           | Q(target_type='review', review__isnull=False)
                           | Q(target_type='user', reported_user__isnull=False)),
                name='report_target_matches_type',
            ),
        ]

    def __str__(self):
        return f'Report #{self.pk} ({self.get_target_type_display()})'

    @property
    def target(self):
        return {'course': self.course, 'review': self.review, 'user': self.reported_user}[self.target_type]
