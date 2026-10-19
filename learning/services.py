import secrets
import string

from django.db import IntegrityError, transaction
from django.utils import timezone

from notifications.models import Notification
from notifications.services import notify

from .models import Certificate, Enrollment, LessonCompletion


class EnrollmentError(Exception):
    pass


def get_active_enrollment(user, course):
    if not user.is_authenticated:
        return None
    return Enrollment.objects.filter(student=user, course=course, status=Enrollment.Status.ACTIVE).first()


def can_manage_course(user, course):
    return user.is_authenticated and (course.instructor_id == user.id or user.is_platform_admin)


def can_access_content(user, course):
    return can_manage_course(user, course) or get_active_enrollment(user, course) is not None


def can_view_lesson(user, lesson):
    course = lesson.section.course
    return (lesson.is_preview and course.is_published) or can_access_content(user, course)


@transaction.atomic
def enroll(student, course, source, order=None):
    if course.instructor_id == student.id:
        raise EnrollmentError('Instructors cannot enrol in their own course.')
    existing = Enrollment.objects.select_for_update().filter(student=student, course=course).first()
    if existing:
        if existing.is_active:
            raise EnrollmentError('You are already enrolled in this course.')
        existing.status = Enrollment.Status.ACTIVE
        existing.source = source
        existing.order = order
        existing.save(update_fields=['status', 'source', 'order'])
        enrollment = existing
    else:
        try:
            with transaction.atomic():
                enrollment = Enrollment.objects.create(student=student, course=course, source=source, order=order)
        except IntegrityError:
            raise EnrollmentError('You are already enrolled in this course.')

    notify(course.instructor, f'New enrolment in {course.title}',
           f'{student.display_name} enrolled ({enrollment.get_source_display().lower()}).',
           url=f'/teach/courses/{course.pk}/students/', kind=Notification.Kind.ENROLLMENT)
    recalculate_progress(enrollment)
    return enrollment


def completed_lesson_ids(enrollment):
    return set(enrollment.completions.values_list('lesson_id', flat=True))


def passed_quiz_ids(enrollment):
    from assessments.models import QuizAttempt
    return set(QuizAttempt.objects.filter(student=enrollment.student, quiz__course=enrollment.course,
                                          passed=True).values_list('quiz_id', flat=True))


def progress_breakdown(enrollment):
    """Progress = (required lessons done + required quizzes passed) / total required items."""
    course = enrollment.course
    lesson_ids = set(course.required_lessons().values_list('id', flat=True))
    quiz_ids = set(course.required_quizzes().values_list('id', flat=True))
    done_lessons = completed_lesson_ids(enrollment) & lesson_ids
    passed = passed_quiz_ids(enrollment) & quiz_ids
    total = len(lesson_ids) + len(quiz_ids)
    done = len(done_lessons) + len(passed)
    return {
        'lessons_total': len(lesson_ids), 'lessons_done': len(done_lessons),
        'quizzes_total': len(quiz_ids), 'quizzes_passed': len(passed),
        'total': total, 'done': done,
        'percent': (done * 100 // total) if total else 0,
        'requirements_met': total > 0 and done == total,
    }


def recalculate_progress(enrollment):
    data = progress_breakdown(enrollment)
    fields = []
    if enrollment.progress_percent != data['percent']:
        enrollment.progress_percent = data['percent']
        fields.append('progress_percent')
    newly_completed = data['requirements_met'] and enrollment.completed_at is None
    if newly_completed:
        enrollment.completed_at = timezone.now()
        fields.append('completed_at')
    if fields:
        enrollment.save(update_fields=fields)
    if newly_completed and enrollment.is_active:
        notify(enrollment.student, f'You completed {enrollment.course.title}!',
               'Congratulations on finishing the course.', url='/learn/certificates/',
               kind=Notification.Kind.CERTIFICATE)
        if enrollment.course.certificate_enabled:
            issue_certificate(enrollment)
    return data


def lesson_is_unlocked(enrollment, lesson, ordered_lessons=None, done_ids=None):
    course = enrollment.course
    if not course.sequential_progression:
        return True
    ordered_lessons = ordered_lessons if ordered_lessons is not None else list(course.lessons())
    done_ids = done_ids if done_ids is not None else completed_lesson_ids(enrollment)
    for earlier in ordered_lessons:
        if earlier.id == lesson.id:
            return True
        if earlier.is_required and earlier.id not in done_ids:
            return False
    return True


def mark_lesson_complete(enrollment, lesson, *, by_quiz=False):
    if lesson.section.course_id != enrollment.course_id:
        raise EnrollmentError('That lesson does not belong to this course.')
    if not enrollment.is_active:
        raise EnrollmentError('Your enrolment is not active.')
    if lesson.completion_rule == lesson.CompletionRule.QUIZ_PASS and not by_quiz and lesson.quizzes.filter(is_published=True).exists():
        raise EnrollmentError('This lesson is completed by passing its quiz.')
    if not lesson_is_unlocked(enrollment, lesson):
        raise EnrollmentError('Complete the previous lessons first.')
    LessonCompletion.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    return recalculate_progress(enrollment)


def touch_lesson(enrollment, lesson):
    enrollment.last_lesson = lesson
    enrollment.last_accessed_at = timezone.now()
    enrollment.save(update_fields=['last_lesson', 'last_accessed_at'])


def resume_lesson(enrollment):
    if enrollment.last_lesson_id and enrollment.last_lesson.section.course_id == enrollment.course_id:
        return enrollment.last_lesson
    done = completed_lesson_ids(enrollment)
    lessons = list(enrollment.course.lessons())
    for lesson in lessons:
        if lesson.id not in done:
            return lesson
    return lessons[0] if lessons else None


def _certificate_number():
    alphabet = string.ascii_uppercase + string.digits
    body = ''.join(secrets.choice(alphabet) for _ in range(12))
    return f'ESK-{body[:4]}-{body[4:8]}-{body[8:]}'


def issue_certificate(enrollment):
    """Returns the certificate, creating it if the course is complete."""
    existing = Certificate.objects.filter(enrollment=enrollment).first()
    if existing:
        return existing
    course = enrollment.course
    if not (enrollment.is_active and course.certificate_enabled):
        return None
    if not progress_breakdown(enrollment)['requirements_met'] and enrollment.completed_at is None:
        return None
    for _ in range(5):
        try:
            with transaction.atomic():
                return Certificate.objects.create(
                    enrollment=enrollment,
                    certificate_number=_certificate_number(),
                    student_name=enrollment.student.display_name,
                    course_title=course.title,
                    instructor_name=course.instructor.display_name,
                )
        except IntegrityError:
            existing = Certificate.objects.filter(enrollment=enrollment).first()
            if existing:
                return existing
    raise RuntimeError('Could not allocate a unique certificate number.')
