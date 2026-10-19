from django.db import transaction
from django.utils import timezone

from core.audit import log_action
from core.models import PlatformSettings
from learning.services import get_active_enrollment
from notifications.models import Notification
from notifications.services import notify

from .models import Course, ModerationDecision, Review

S = Course.Status
A = ModerationDecision.Action


class ModerationError(Exception):
    pass


def readiness_problems(course):
    problems = []
    settings = PlatformSettings.load()
    lessons = list(course.lessons())
    if not course.sections.exists():
        problems.append('Add at least one section.')
    if not lessons:
        problems.append('Add at least one lesson.')
    for lesson in lessons:
        if lesson.lesson_type == lesson.LessonType.VIDEO and not (lesson.video_file or lesson.video_url):
            problems.append(f'Lesson "{lesson.title}" is a video lesson without a video.')
        if lesson.lesson_type == lesson.LessonType.ARTICLE and not lesson.content.strip():
            problems.append(f'Lesson "{lesson.title}" has no article text.')
    if not course.objectives_list:
        problems.append('List at least one learning objective.')
    if course.price > settings.max_course_price:
        problems.append(f'Price exceeds the platform maximum of ${settings.max_course_price}.')
    if course.discount_price is not None and not settings.allow_discounts:
        problems.append('Discounts are currently disabled by the platform.')
    for quiz in course.quizzes.filter(is_published=True):
        problems.extend(quiz.validation_errors())
    return problems


def _transition(course, actor, action, to_status, reason='', request=None):
    from_status = course.status
    course.status = to_status
    fields = ['status', 'updated_at']
    if to_status == S.SUBMITTED:
        course.submitted_at = timezone.now()
        fields.append('submitted_at')
    if to_status == S.PUBLISHED and course.published_at is None:
        course.published_at = timezone.now()
        fields.append('published_at')
    if to_status != S.PUBLISHED and course.is_featured:
        course.is_featured = False
        fields.append('is_featured')
    course.save(update_fields=fields)
    decision = ModerationDecision.objects.create(course=course, actor=actor, action=action,
                                                 from_status=from_status, to_status=to_status, reason=reason)
    log_action(actor, f'course.{action}', course, {'from': from_status, 'to': to_status, 'reason': reason},
               request=request)
    return decision


@transaction.atomic
def submit_for_review(course, instructor, note='', request=None):
    if course.instructor_id != instructor.id:
        raise ModerationError('You can only submit your own courses.')
    if not course.can_be_submitted:
        raise ModerationError(f'A course that is {course.get_status_display().lower()} cannot be submitted.')
    if problems := readiness_problems(course):
        raise ModerationError(' '.join(problems))
    if PlatformSettings.load().require_course_approval:
        _transition(course, instructor, A.SUBMITTED, S.SUBMITTED, note, request)
        from accounts.models import User
        for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
            notify(admin, f'Course submitted for review: {course.title}',
                   f'By {instructor.display_name}.', url=f'/manage/courses/{course.pk}/',
                   kind=Notification.Kind.MODERATION)
    else:
        _transition(course, instructor, A.SUBMITTED, S.SUBMITTED, note, request)
        _transition(course, None, A.APPROVED, S.PUBLISHED, 'Automatically published (approval not required).',
                    request)
    return course


@transaction.atomic
def instructor_archive(course, instructor, request=None):
    if course.instructor_id != instructor.id:
        raise ModerationError('You can only archive your own courses.')
    if course.status == S.ARCHIVED:
        raise ModerationError('This course is already archived.')
    _transition(course, instructor, A.ARCHIVED, S.ARCHIVED, 'Archived by instructor.', request)


@transaction.atomic
def instructor_restore(course, instructor, request=None):
    if course.instructor_id != instructor.id or course.status != S.ARCHIVED:
        raise ModerationError('Only your archived courses can be restored.')
    _transition(course, instructor, A.RESTORED, S.DRAFT, 'Restored to draft by instructor.', request)


def after_instructor_edit(course, instructor, request=None):
    if course.status == S.PUBLISHED and PlatformSettings.load().reapprove_published_edits:
        _transition(course, instructor, A.SUBMITTED, S.SUBMITTED,
                    'Published course edited; re-review required by policy.', request)
        return True
    return False


ADMIN_ACTIONS = {
    # action: (allowed from, new status, reason required)
    A.APPROVED: ({S.SUBMITTED, S.UNPUBLISHED}, S.PUBLISHED, False),
    A.CHANGES_REQUESTED: ({S.SUBMITTED}, S.CHANGES_REQUESTED, True),
    A.REJECTED: ({S.SUBMITTED}, S.REJECTED, True),
    A.UNPUBLISHED: ({S.PUBLISHED}, S.UNPUBLISHED, True),
    A.ARCHIVED: ({S.PUBLISHED, S.UNPUBLISHED, S.REJECTED, S.DRAFT, S.CHANGES_REQUESTED, S.SUBMITTED},
                 S.ARCHIVED, True),
}


def admin_available_actions(course):
    return [action for action, (allowed, _, _) in ADMIN_ACTIONS.items() if course.status in allowed]


@transaction.atomic
def moderate(course, admin, action, reason='', request=None):
    if not admin.is_platform_admin:
        raise ModerationError('Only administrators can moderate courses.')
    if action not in ADMIN_ACTIONS:
        raise ModerationError('Unknown moderation action.')
    allowed, to_status, needs_reason = ADMIN_ACTIONS[action]
    if course.status not in allowed:
        raise ModerationError(f'Cannot {A(action).label.lower()} a course that is {course.get_status_display().lower()}.')
    reason = (reason or '').strip()
    if needs_reason and not reason:
        raise ModerationError('Please give a reason so the instructor knows what to change.')
    if action == A.APPROVED and (problems := readiness_problems(course)):
        raise ModerationError('Course is not ready: ' + ' '.join(problems))
    decision = _transition(course, admin, action, to_status, reason, request)
    notify(course.instructor, f'{course.title}: {decision.get_action_display()}',
           reason or 'Your course is now live in the marketplace.',
           url=f'/teach/courses/{course.pk}/', kind=Notification.Kind.MODERATION)
    return decision


def review_eligibility(user, course):
    """Returns (allowed, reason_if_not)."""
    if not user.is_authenticated:
        return False, 'Log in to review this course.'
    enrollment = get_active_enrollment(user, course)
    if enrollment is None:
        return False, 'Only enrolled students can review this course.'
    minimum = PlatformSettings.load().review_min_progress
    if enrollment.progress_percent < minimum:
        return False, f'Complete at least {minimum}% of the course to leave a review.'
    return True, ''


def save_review(user, course, rating, comment):
    allowed, reason = review_eligibility(user, course)
    if not allowed:
        raise ModerationError(reason)
    review, created = Review.objects.update_or_create(
        course=course, student=user, defaults={'rating': rating, 'comment': comment})
    if created:
        notify(course.instructor, f'New {rating}★ review on {course.title}',
               comment[:140], url=f'/teach/courses/{course.pk}/reviews/', kind=Notification.Kind.REVIEW)
    return review, created
