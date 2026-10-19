from datetime import timedelta

from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.testing import make_course, make_quiz, make_user
from learning import services as learning
from learning.models import Enrollment

from . import services
from .models import QuizAttempt


def answers(question, *options):
    data = QueryDict(mutable=True)
    data.setlist(f'q{question.pk}', [str(o.pk) for o in options])
    return data


class QuizRuleTests(TestCase):
    def setUp(self):
        self.course = make_course()
        self.student = make_user()
        learning.enroll(self.student, self.course, Enrollment.Source.ADMIN)
        self.quiz, self.question, self.right, self.wrong = make_quiz(self.course, max_attempts=2)

    def test_attempt_limit_enforced_on_server(self):
        for _ in range(2):
            attempt = services.start_attempt(self.quiz, self.student)
            services.submit_attempt(attempt.pk, self.student, answers(self.question, self.wrong))
        with self.assertRaises(services.QuizError):
            services.start_attempt(self.quiz, self.student)
        self.client.force_login(self.student)
        self.client.post(reverse('assessments:start', args=[self.course.slug, self.quiz.pk]))
        self.assertEqual(QuizAttempt.objects.count(), 2)

    def test_cannot_submit_twice(self):
        attempt = services.start_attempt(self.quiz, self.student)
        services.submit_attempt(attempt.pk, self.student, answers(self.question, self.right))
        with self.assertRaises(services.QuizError):
            services.submit_attempt(attempt.pk, self.student, answers(self.question, self.right))

    def test_grading_and_tampered_option_ids(self):
        attempt = services.start_attempt(self.quiz, self.student)
        _, other_q, other_right, _ = make_quiz(make_course())
        services.submit_attempt(attempt.pk, self.student, answers(self.question, other_right))
        attempt.refresh_from_db()
        self.assertEqual(attempt.score_percent, 0)
        attempt = services.start_attempt(self.quiz, self.student)
        services.submit_attempt(attempt.pk, self.student, answers(self.question, self.right))
        attempt.refresh_from_db()
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.score_percent, 100)

    def test_selecting_every_option_is_not_correct(self):
        attempt = services.start_attempt(self.quiz, self.student)
        services.submit_attempt(attempt.pk, self.student, answers(self.question, self.right, self.wrong))
        attempt.refresh_from_db()
        self.assertFalse(attempt.passed)

    def test_late_submission_is_expired(self):
        self.quiz.time_limit_minutes = 5
        self.quiz.save()
        attempt = services.start_attempt(self.quiz, self.student)
        QuizAttempt.objects.filter(pk=attempt.pk).update(deadline=timezone.now() - timedelta(minutes=10))
        attempt = services.submit_attempt(attempt.pk, self.student, answers(self.question, self.right))
        self.assertEqual(attempt.status, QuizAttempt.Status.EXPIRED)
        self.assertFalse(attempt.passed)

    def test_quiz_page_does_not_leak_correct_answers(self):
        self.client.force_login(self.student)
        attempt = services.start_attempt(self.quiz, self.student)
        html = self.client.get(reverse('assessments:take', args=[self.course.slug, attempt.pk])).content.decode()
        self.assertNotIn('is_correct', html)
        self.assertNotIn('correct', html.lower().replace('incorrect', ''))

    def test_answers_hidden_until_final_attempt_when_configured(self):
        attempt = services.start_attempt(self.quiz, self.student)
        services.submit_attempt(attempt.pk, self.student, answers(self.question, self.wrong))
        attempt.refresh_from_db()
        self.assertFalse(services.can_reveal_answers(attempt))  # one attempt left, not passed
        attempt2 = services.start_attempt(self.quiz, self.student)
        services.submit_attempt(attempt2.pk, self.student, answers(self.question, self.wrong))
        attempt2.refresh_from_db()
        self.assertTrue(services.can_reveal_answers(attempt2))  # attempts exhausted

    def test_unenrolled_student_cannot_start(self):
        outsider = make_user()
        with self.assertRaises(services.QuizError):
            services.start_attempt(self.quiz, outsider)
