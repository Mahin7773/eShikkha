from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from assessments.models import Quiz, QuizAttempt
from core.files import serve_file
from core.permissions import student_required
from courses.models import Course, Lesson, LessonResource

from . import services
from .certificates import render_certificate_pdf
from .models import Certificate, Enrollment


@student_required
def dashboard(request):
    enrollments = (request.user.enrollments.filter(status=Enrollment.Status.ACTIVE)
                   .select_related('course__instructor', 'course__category', 'last_lesson'))
    in_progress = [e for e in enrollments if not e.is_completed]
    completed = [e for e in enrollments if e.is_completed]
    tab = request.GET.get('tab', 'progress')
    attempts = (QuizAttempt.objects.filter(student=request.user)
                .exclude(status=QuizAttempt.Status.IN_PROGRESS).select_related('quiz__course')[:6])
    continue_learning = max(in_progress, key=lambda e: e.last_accessed_at or e.enrolled_at, default=None)
    return render(request, 'learning/dashboard.html', {
        'tab': tab,
        'in_progress': in_progress,
        'completed': completed,
        'continue_learning': continue_learning,
        'recent_attempts': attempts,
        'certificates': Certificate.objects.filter(enrollment__student=request.user, is_revoked=False),
        'stats': {
            'enrolled': len(enrollments),
            'completed': len(completed),
            'lessons_done': sum(e.completions.count() for e in enrollments),
            'quizzes_passed': QuizAttempt.objects.filter(student=request.user, passed=True)
                                                 .values('quiz').distinct().count(),
        },
    })


@student_required
def certificates(request):
    certs = (Certificate.objects.filter(enrollment__student=request.user)
             .select_related('enrollment__course'))
    return render(request, 'learning/certificates.html', {'certificates': certs})


@login_required
def resume(request, slug):
    course = get_object_or_404(Course, slug=slug)
    enrollment = services.get_active_enrollment(request.user, course)
    if enrollment is None and not services.can_manage_course(request.user, course):
        messages.info(request, 'Enrol in this course to start learning.')
        return redirect(course.get_absolute_url())
    lesson = services.resume_lesson(enrollment) if enrollment else course.lessons().first()
    if lesson is None:
        messages.info(request, 'This course has no lessons yet.')
        return redirect(course.get_absolute_url())
    return redirect('learning:lesson', course.slug, lesson.pk)


def _build_outline(course, enrollment, current, viewer_can_access):
    sections = course.sections.prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order', 'id')
                 .prefetch_related(Prefetch('quizzes', queryset=Quiz.objects.filter(is_published=True)))))
    ordered = [lesson for s in sections for lesson in s.lessons.all()]
    done = services.completed_lesson_ids(enrollment) if enrollment else set()
    passed = services.passed_quiz_ids(enrollment) if enrollment else set()

    outline = []
    for section in sections:
        items = []
        for lesson in section.lessons.all():
            if lesson.id == current.id:
                state = 'current'
            elif not viewer_can_access and not lesson.is_preview:
                state = 'locked'
            elif enrollment and not services.lesson_is_unlocked(enrollment, lesson, ordered, done):
                state = 'locked'
            elif lesson.id in done:
                state = 'completed'
            else:
                state = 'available'
            items.append({'lesson': lesson, 'state': state, 'done': lesson.id in done,
                          'quizzes': [{'quiz': q, 'passed': q.id in passed} for q in lesson.quizzes.all()]})
        outline.append({'section': section, 'items': items,
                        'has_current': any(i['state'] == 'current' for i in items),
                        'done': sum(1 for i in items if i['done']), 'total': len(items)})
    final_quizzes = [{'quiz': q, 'passed': q.id in passed}
                     for q in course.quizzes.filter(is_published=True, lesson__isnull=True)]
    return outline, ordered, final_quizzes, done


def lesson_view(request, slug, lesson_id):
    course = get_object_or_404(Course.objects.select_related('instructor'), slug=slug)
    lesson = get_object_or_404(Lesson.objects.select_related('section'), pk=lesson_id, section__course=course)
    user = request.user
    can_access = services.can_access_content(user, course)
    if not (can_access or (lesson.is_preview and course.is_published)):
        if not user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        messages.info(request, 'Enrol in this course to unlock this lesson.')
        return redirect(course.get_absolute_url())

    enrollment = services.get_active_enrollment(user, course)
    outline, ordered, final_quizzes, done = _build_outline(course, enrollment, lesson, can_access)
    if enrollment and not services.lesson_is_unlocked(enrollment, lesson, ordered, done):
        messages.info(request, 'Complete the previous lessons to unlock this one.')
        return redirect('learning:resume', course.slug)
    if enrollment:
        services.touch_lesson(enrollment, lesson)

    index = ordered.index(lesson)
    prev_lesson = ordered[index - 1] if index > 0 else None
    next_lesson = ordered[index + 1] if index + 1 < len(ordered) else None
    lesson_quizzes = [i['quizzes'] for s in outline for i in s['items'] if i['lesson'].id == lesson.id][0]
    manual_completion = not (lesson.completion_rule == Lesson.CompletionRule.QUIZ_PASS and lesson_quizzes)

    return render(request, 'learning/player.html', {
        'course': course,
        'lesson': lesson,
        'outline': outline,
        'final_quizzes': final_quizzes,
        'enrollment': enrollment,
        'is_preview_mode': enrollment is None,
        'can_access': can_access,
        'is_completed': lesson.id in done,
        'manual_completion': manual_completion,
        'lesson_quizzes': lesson_quizzes,
        'quiz_count': len(lesson_quizzes) + len(final_quizzes),
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'progress': services.progress_breakdown(enrollment) if enrollment else None,
        'resources': lesson.resources.all(),
        'video_src': reverse('learning:lesson_video', args=[lesson.pk]) if lesson.video_file else lesson.video_url,
    })


@login_required
@require_POST
def complete_lesson(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug)
    lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
    enrollment = services.get_active_enrollment(request.user, course)
    if enrollment is None:
        raise PermissionDenied
    was_completed = enrollment.is_completed
    try:
        services.mark_lesson_complete(enrollment, lesson)
    except services.EnrollmentError as exc:
        messages.error(request, str(exc))
        return redirect('learning:lesson', slug, lesson.pk)
    enrollment.refresh_from_db()
    if enrollment.is_completed and not was_completed:
        messages.success(request, 'Course complete! Your certificate is ready in the Certificates section.'
                         if course.certificate_enabled else 'Course complete. Congratulations!')
        return redirect('learning:dashboard')
    messages.success(request, f'"{lesson.title}" marked as complete.')
    next_id = request.POST.get('next_lesson')
    if next_id and Lesson.objects.filter(pk=next_id, section__course=course).exists():
        return redirect('learning:lesson', slug, next_id)
    return redirect('learning:lesson', slug, lesson.pk)


def lesson_video(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('section__course'), pk=lesson_id)
    if not services.can_view_lesson(request.user, lesson):
        raise PermissionDenied
    return serve_file(request, lesson.video_file)


def resource_download(request, resource_id):
    resource = get_object_or_404(LessonResource.objects.select_related('lesson__section__course'), pk=resource_id)
    if not services.can_view_lesson(request.user, resource.lesson):
        raise PermissionDenied
    if resource.url and not resource.file:
        return redirect(resource.url)
    return serve_file(request, resource.file, as_attachment=True)


@login_required
def certificate_pdf(request, number):
    certificate = get_object_or_404(Certificate.objects.select_related('enrollment'), certificate_number=number)
    if certificate.enrollment.student_id != request.user.id and not request.user.is_platform_admin:
        raise PermissionDenied
    if certificate.is_revoked:
        messages.error(request, 'This certificate has been revoked.')
        return redirect('learning:certificates')
    verify_url = request.build_absolute_uri(certificate.get_absolute_url())
    pdf = render_certificate_pdf(certificate, verify_url)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="eShikkha-certificate-{certificate.certificate_number}.pdf"'
    return response


def verify_certificate(request, number=None):
    number = (number or request.GET.get('id', '')).strip().upper()
    certificate = None
    if number:
        certificate = Certificate.objects.filter(certificate_number=number).first()
    return render(request, 'learning/verify.html', {'number': number, 'certificate': certificate,
                                                    'searched': bool(number)})
