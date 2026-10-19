import random
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from learning import services as learning

from .models import AttemptAnswer, Question, Quiz, QuizAttempt


class QuizError(Exception):
    pass


def attempts_for(quiz, student):
    return QuizAttempt.objects.filter(quiz=quiz, student=student)


def attempts_used(quiz, student):
    return attempts_for(quiz, student).count()


def attempts_remaining(quiz, student):
    if quiz.unlimited_attempts:
        return None
    return max(quiz.max_attempts - attempts_used(quiz, student), 0)


def has_passed(quiz, student):
    return attempts_for(quiz, student).filter(passed=True).exists()


def best_attempt(quiz, student):
    return (attempts_for(quiz, student).exclude(status=QuizAttempt.Status.IN_PROGRESS)
            .order_by('-score_percent', '-submitted_at').first())


def _grace():
    return timedelta(seconds=settings.QUIZ_SUBMISSION_GRACE_SECONDS)


def expire_if_overdue(attempt):
    """Close an attempt that ran past its deadline. Returns True if it did."""
    if attempt.is_open and attempt.deadline and timezone.now() > attempt.deadline + _grace():
        _grade(attempt, {}, status=QuizAttempt.Status.EXPIRED)
        return True
    return False


def get_open_attempt(quiz, student):
    attempt = attempts_for(quiz, student).filter(status=QuizAttempt.Status.IN_PROGRESS).first()
    if attempt and expire_if_overdue(attempt):
        return None
    return attempt


def check_can_start(quiz, student):
    enrollment = learning.get_active_enrollment(student, quiz.course)
    if enrollment is None:
        raise QuizError('You must be enrolled in this course to take the quiz.')
    if not quiz.is_published:
        raise QuizError('This quiz is not available.')
    if not quiz.questions.exists():
        raise QuizError('This quiz has no questions yet.')
    remaining = attempts_remaining(quiz, student)
    if remaining is not None and remaining <= 0:
        raise QuizError('You have used all attempts for this quiz.')
    return enrollment


@transaction.atomic
def start_attempt(quiz, student):
    open_attempt = get_open_attempt(quiz, student)
    if open_attempt:
        return open_attempt
    check_can_start(quiz, student)
    question_ids = list(quiz.questions.values_list('id', flat=True))
    if quiz.shuffle_questions:
        random.shuffle(question_ids)
    now = timezone.now()
    try:
        with transaction.atomic():
            return QuizAttempt.objects.create(
                quiz=quiz, student=student,
                attempt_number=attempts_used(quiz, student) + 1,
                question_order=question_ids,
                deadline=now + timedelta(minutes=quiz.time_limit_minutes) if quiz.time_limit_minutes else None,
                points_possible=sum(Question.objects.filter(id__in=question_ids).values_list('points', flat=True)),
            )
    except IntegrityError:
        # another request created it first (double click)
        open_attempt = get_open_attempt(quiz, student)
        if open_attempt:
            return open_attempt
        raise QuizError('Could not start the quiz. Please try again.')


def ordered_questions(attempt):
    questions = {q.id: q for q in attempt.quiz.questions.prefetch_related('options')}
    return [questions[qid] for qid in attempt.question_order if qid in questions]


def parse_submission(attempt, post_data):
    """Returns {question_id: set(option_ids)}, ignoring ids from other questions."""
    answers = {}
    for question in ordered_questions(attempt):
        valid = {o.id for o in question.options.all()}
        raw = post_data.getlist(f'q{question.id}')
        chosen = set()
        for value in raw:
            try:
                option_id = int(value)
            except (TypeError, ValueError):
                continue
            if option_id in valid:
                chosen.add(option_id)
        if not question.is_multi_select and len(chosen) > 1:
            chosen = set()  # single-answer question given several options: invalid
        answers[question.id] = chosen
    return answers


@transaction.atomic
def submit_attempt(attempt_id, student, post_data):
    attempt = (QuizAttempt.objects.select_for_update()
               .select_related('quiz__course').get(pk=attempt_id, student=student))
    if not attempt.is_open:
        raise QuizError('This attempt has already been submitted.')
    if attempt.deadline and timezone.now() > attempt.deadline + _grace():
        _grade(attempt, {}, status=QuizAttempt.Status.EXPIRED)
    else:
        _grade(attempt, parse_submission(attempt, post_data), status=QuizAttempt.Status.SUBMITTED)
    return attempt


def _grade(attempt, answers, status):
    earned = 0
    possible = 0
    for question in ordered_questions(attempt):
        selected = answers.get(question.id, set())
        correct = bool(selected) and selected == question.correct_option_ids()
        points = question.points if correct else 0
        earned += points
        possible += question.points
        answer, _ = AttemptAnswer.objects.update_or_create(
            attempt=attempt, question=question, defaults={'is_correct': correct, 'points_awarded': points})
        answer.selected_options.set(selected)

    score = (Decimal(earned * 100) / Decimal(possible)).quantize(Decimal('0.01'), ROUND_HALF_UP) if possible else Decimal(0)
    attempt.points_earned = earned
    attempt.points_possible = possible
    attempt.score_percent = score
    attempt.passed = status == QuizAttempt.Status.SUBMITTED and score >= attempt.quiz.passing_score
    attempt.status = status
    attempt.submitted_at = timezone.now()
    attempt.save()

    enrollment = learning.get_active_enrollment(attempt.student, attempt.quiz.course)
    if enrollment:
        lesson = attempt.quiz.lesson
        if attempt.passed and lesson and lesson.completion_rule == lesson.CompletionRule.QUIZ_PASS:
            try:
                learning.mark_lesson_complete(enrollment, lesson, by_quiz=True)
            except learning.EnrollmentError:
                pass  # e.g. sequential lock; progress still recalculated below
        learning.recalculate_progress(enrollment)


def can_reveal_answers(attempt):
    quiz = attempt.quiz
    if attempt.is_open:
        return False
    if quiz.result_visibility == Quiz.ResultVisibility.FULL:
        return True
    if quiz.result_visibility == Quiz.ResultVisibility.AFTER_FINAL:
        if has_passed(quiz, attempt.student):
            return True
        return not quiz.unlimited_attempts and attempts_remaining(quiz, attempt.student) == 0
    return False
