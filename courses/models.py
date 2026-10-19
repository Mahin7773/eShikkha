import re
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, F, IntegerField, OuterRef, Q, Subquery, FloatField
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from core.validators import (
    validate_image_extension, validate_image_size, validate_resource_extension,
    validate_resource_size, validate_video_extension, validate_video_size,
)


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('courses:list') + f'?category={self.slug}'


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Course.Status.PUBLISHED)

    def with_stats(self):
        # subqueries instead of joins so the counts don't multiply each other
        from learning.models import Enrollment

        students = (Enrollment.objects.filter(course=OuterRef('pk'), status=Enrollment.Status.ACTIVE)
                    .order_by().values('course').annotate(n=Count('pk')).values('n'))
        visible_reviews = Review.objects.filter(course=OuterRef('pk'), is_hidden=False).order_by().values('course')
        return self.annotate(
            students_count=Coalesce(Subquery(students, output_field=IntegerField()), 0),
            rating_avg=Coalesce(Subquery(visible_reviews.annotate(a=Avg('rating')).values('a'),
                                         output_field=FloatField()), 0.0),
            rating_count=Coalesce(Subquery(visible_reviews.annotate(n=Count('pk')).values('n'),
                                           output_field=IntegerField()), 0),
        )


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted for review'
        CHANGES_REQUESTED = 'changes_requested', 'Changes requested'
        REJECTED = 'rejected', 'Rejected'
        PUBLISHED = 'published', 'Published'
        UNPUBLISHED = 'unpublished', 'Unpublished'
        ARCHIVED = 'archived', 'Archived'

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        ALL = 'all', 'All levels'

    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='courses_taught')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='courses')
    tags = models.ManyToManyField(Tag, blank=True, related_name='courses')

    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    learning_objectives = models.TextField(help_text='One objective per line.')
    prerequisites = models.TextField(blank=True, help_text='One requirement per line.')
    target_audience = models.TextField(blank=True, help_text='Who is this course for? One per line.')
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.BEGINNER)
    language = models.CharField(max_length=40, default='English')

    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True,
                                  validators=[validate_image_extension, validate_image_size])
    promo_video = models.FileField(upload_to='courses/promo/', blank=True,
                                   validators=[validate_video_extension, validate_video_size])
    promo_video_url = models.URLField(blank=True, help_text='YouTube, Vimeo or direct .mp4 link.')

    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'),
                                validators=[MinValueValidator(0)])
    discount_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(0)])
    discount_ends_at = models.DateTimeField(null=True, blank=True)

    sequential_progression = models.BooleanField(
        default=False, help_text='Lessons unlock only after the previous required lesson is completed.')
    require_quizzes_for_completion = models.BooleanField(
        default=True, help_text='Students must pass every required quiz to complete the course.')
    certificate_enabled = models.BooleanField(default=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = CourseQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['category', 'status']),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name='course_price_non_negative'),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__gte=0, discount_price__lt=F('price')),
                name='course_discount_below_price',
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('courses:detail', args=[self.slug])

    @staticmethod
    def _lines(text):
        return [line.strip(' -•\t') for line in (text or '').splitlines() if line.strip(' -•\t')]

    @property
    def objectives_list(self):
        return self._lines(self.learning_objectives)

    @property
    def prerequisites_list(self):
        return self._lines(self.prerequisites)

    @property
    def audience_list(self):
        return self._lines(self.target_audience)

    def lessons(self):
        return Lesson.objects.filter(section__course=self).order_by('section__order', 'section_id', 'order', 'id')

    def required_lessons(self):
        # if nothing is marked required, every lesson counts
        lessons = self.lessons()
        required = lessons.filter(is_required=True)
        return required if required.exists() else lessons

    def required_quizzes(self):
        if not self.require_quizzes_for_completion:
            return self.quizzes.none()
        return self.quizzes.filter(is_published=True, is_required=True)

    @property
    def promo_embed_url(self):
        return embed_url(self.promo_video_url)

    @property
    def total_duration_minutes(self):
        return self.lessons().aggregate(t=models.Sum('duration_minutes'))['t'] or 0

    @property
    def has_active_discount(self):
        return (self.discount_price is not None and self.discount_price < self.price
                and (self.discount_ends_at is None or self.discount_ends_at > timezone.now()))

    @property
    def current_price(self):
        return self.discount_price if self.has_active_discount else self.price

    @property
    def discount_amount(self):
        return self.price - self.current_price

    @property
    def discount_percent(self):
        if not self.has_active_discount or not self.price:
            return 0
        return int(round((1 - self.discount_price / self.price) * 100))

    @property
    def is_free(self):
        return self.current_price == 0

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def can_be_submitted(self):
        return self.status in {self.Status.DRAFT, self.Status.CHANGES_REQUESTED,
                               self.Status.REJECTED, self.Status.UNPUBLISHED}

    @property
    def status_tone(self):
        return {
            'draft': 'neutral', 'submitted': 'info', 'changes_requested': 'warning',
            'rejected': 'danger', 'published': 'success', 'unpublished': 'neutral',
            'archived': 'neutral',
        }[self.status]

    @property
    def latest_feedback(self):
        return (self.moderation_decisions.exclude(reason='')
                .exclude(action=ModerationDecision.Action.SUBMITTED).first())


class Section(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.title


class Lesson(models.Model):
    class LessonType(models.TextChoices):
        VIDEO = 'video', 'Video'
        ARTICLE = 'article', 'Article / reading'

    class CompletionRule(models.TextChoices):
        MANUAL = 'manual', 'Student marks the lesson as complete'
        QUIZ_PASS = 'quiz_pass', 'Completed automatically when the lesson quiz is passed'

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=140)
    lesson_type = models.CharField(max_length=10, choices=LessonType.choices, default=LessonType.VIDEO)
    video_file = models.FileField(upload_to='courses/videos/', blank=True,
                                  validators=[validate_video_extension, validate_video_size])
    video_url = models.URLField(blank=True, help_text='YouTube, Vimeo or direct video link.')
    content = models.TextField(blank=True, help_text='Lesson overview or article text.')
    duration_minutes = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False, help_text='Free preview for visitors.')
    is_required = models.BooleanField(default=True, help_text='Counts towards course completion.')
    completion_rule = models.CharField(max_length=10, choices=CompletionRule.choices,
                                       default=CompletionRule.MANUAL)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.title

    @property
    def video_kind(self):
        if self.video_file:
            return 'file'
        if not self.video_url:
            return None
        return 'embed' if embed_url(self.video_url) else 'direct'

    @property
    def embed_url(self):
        return embed_url(self.video_url)


_YOUTUBE = re.compile(r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})')
_VIMEO = re.compile(r'vimeo\.com/(?:video/)?(\d+)')


def embed_url(url):
    if not url:
        return None
    if m := _YOUTUBE.search(url):
        return f'https://www.youtube-nocookie.com/embed/{m.group(1)}'
    if m := _VIMEO.search(url):
        return f'https://player.vimeo.com/video/{m.group(1)}'
    return None


class LessonResource(models.Model):
    class ResourceType(models.TextChoices):
        PDF = 'pdf', 'PDF / lecture notes'
        SLIDES = 'slides', 'Slides'
        DOCUMENT = 'document', 'Document'
        FILE = 'file', 'Downloadable file'
        LINK = 'link', 'External link'

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=140)
    resource_type = models.CharField(max_length=10, choices=ResourceType.choices, default=ResourceType.PDF)
    file = models.FileField(upload_to='courses/resources/', blank=True,
                            validators=[validate_resource_extension, validate_resource_size])
    url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=~Q(file='') | ~Q(url=''), name='resource_has_file_or_url'),
        ]

    def __str__(self):
        return self.title


class ModerationDecision(models.Model):
    class Action(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted for review'
        APPROVED = 'approved', 'Approved & published'
        CHANGES_REQUESTED = 'changes_requested', 'Changes requested'
        REJECTED = 'rejected', 'Rejected'
        UNPUBLISHED = 'unpublished', 'Unpublished'
        ARCHIVED = 'archived', 'Archived'
        RESTORED = 'restored', 'Restored to draft'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='moderation_decisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='moderation_decisions')
    action = models.CharField(max_length=20, choices=Action.choices)
    from_status = models.CharField(max_length=20, choices=Course.Status.choices)
    to_status = models.CharField(max_length=20, choices=Course.Status.choices)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.course}: {self.get_action_display()}'


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_hidden = models.BooleanField(default=False)
    hidden_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['course', 'student'], name='one_review_per_student_course'),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5'),
        ]

    def __str__(self):
        return f'{self.rating}★ {self.course} by {self.student}'
