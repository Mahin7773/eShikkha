from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from learning import services as learning

from . import services
from .models import Quiz, QuizAttempt


def _get_quiz(slug, quiz_id):
    return get_object_or_404(Quiz.objects.select_related('course', 'lesson'),
                             pk=quiz_id, course__slug=slug, is_published=True)


@login_required
def quiz_detail(request, slug, quiz_id):
    quiz = _get_quiz(slug, quiz_id)
    user = request.user
    enrollment = learning.get_active_enrollment(user, quiz.course)
    if enrollment is None and not learning.can_manage_course(user, quiz.course):
        messages.info(request, 'Enrol in this course to take its quizzes.')
        return redirect(quiz.course.get_absolute_url())

    open_attempt = services.get_open_attempt(quiz, user) if enrollment else None
    history = services.attempts_for(quiz, user).exclude(status=QuizAttempt.Status.IN_PROGRESS)
    can_start, block_reason = True, ''
    if enrollment is None:
        can_start, block_reason = False, 'Instructor preview: quizzes can only be attempted by enrolled students.'
    elif not open_attempt:
        try:
            services.check_can_start(quiz, user)
        except services.QuizError as exc:
            can_start, block_reason = False, str(exc)

    return render(request, 'assessments/quiz_detail.html', {
        'quiz': quiz, 'course': quiz.course,
        'question_count': quiz.questions.count(),
        'history': history,
        'open_attempt': open_attempt,
        'attempts_used': services.attempts_used(quiz, user),
        'attempts_remaining': services.attempts_remaining(quiz, user),
        'best': services.best_attempt(quiz, user),
        'passed': services.has_passed(quiz, user),
        'can_start': can_start,
        'block_reason': block_reason,
    })


@login_required
@require_POST
def start_quiz(request, slug, quiz_id):
    quiz = _get_quiz(slug, quiz_id)
    try:
        attempt = services.start_attempt(quiz, request.user)
    except services.QuizError as exc:
        messages.error(request, str(exc))
        return redirect('assessments:quiz', slug, quiz.pk)
    return redirect('assessments:take', slug, attempt.pk)


@login_required
def take_quiz(request, slug, attempt_id):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz__course'),
                                pk=attempt_id, student=request.user, quiz__course__slug=slug)
    if learning.get_active_enrollment(request.user, attempt.quiz.course) is None:
        raise PermissionDenied

    if request.method == 'POST':
        try:
            attempt = services.submit_attempt(attempt.pk, request.user, request.POST)
        except services.QuizError as exc:
            messages.error(request, str(exc))
        else:
            if attempt.status == QuizAttempt.Status.EXPIRED:
                messages.error(request, 'Time expired before you submitted, so the attempt was recorded as expired.')
            elif attempt.passed:
                messages.success(request, f'You passed with {attempt.score_percent:.0f}%!')
            else:
                messages.info(request, f'You scored {attempt.score_percent:.0f}%. '
                                       f'{attempt.quiz.passing_score}% is needed to pass.')
        return redirect('assessments:result', slug, attempt.pk)

    if services.expire_if_overdue(attempt) or not attempt.is_open:
        return redirect('assessments:result', slug, attempt.pk)
    return render(request, 'assessments/take.html', {
        'attempt': attempt, 'quiz': attempt.quiz, 'course': attempt.quiz.course,
        'questions': services.ordered_questions(attempt),
    })


@login_required
def attempt_result(request, slug, attempt_id):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz__course', 'quiz__lesson'),
                                pk=attempt_id, quiz__course__slug=slug)
    is_owner = attempt.student_id == request.user.id
    if not (is_owner or learning.can_manage_course(request.user, attempt.quiz.course)):
        raise PermissionDenied
    if attempt.is_open:
        return redirect('assessments:take', slug, attempt.pk)

    reveal = services.can_reveal_answers(attempt) or not is_owner
    answers = {a.question_id: a for a in attempt.answers.prefetch_related('selected_options')}
    rows = []
    for question in services.ordered_questions(attempt):
        answer = answers.get(question.id)
        selected = {o.id for o in answer.selected_options.all()} if answer else set()
        rows.append({'question': question, 'selected': selected,
                     'is_correct': answer.is_correct if answer else False,
                     'points': answer.points_awarded if answer else 0})
    return render(request, 'assessments/result.html', {
        'attempt': attempt, 'quiz': attempt.quiz, 'course': attempt.quiz.course,
        'rows': rows, 'reveal': reveal,
        'show_explanations': reveal and attempt.quiz.show_explanations,
        'attempts_remaining': services.attempts_remaining(attempt.quiz, attempt.student),
        'is_owner': is_owner,
    })
