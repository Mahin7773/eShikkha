from django.test import TestCase
from django.urls import reverse

from assessments import services as quiz_services
from core.testing import make_course, make_quiz, make_user
from courses.models import Lesson

from . import services
from .models import Certificate, Enrollment


class AccessControlTests(TestCase):
    def setUp(self):
        self.course = make_course()
        self.student = make_user()
        self.locked = self.course.lessons().filter(is_preview=False).first()
        self.preview = self.course.lessons().get(is_preview=True)

    def test_preview_lesson_is_public_but_paid_lessons_are_not(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('learning:lesson', args=[self.course.slug, self.preview.pk])).status_code, 200)
        response = self.client.get(reverse('learning:lesson', args=[self.course.slug, self.locked.pk]))
        self.assertRedirects(response, self.course.get_absolute_url())

    def test_protected_resources_require_enrolment(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('learning:lesson_video', args=[self.locked.pk])).status_code, 403)

    def test_cannot_complete_lesson_without_enrolment(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('learning:complete_lesson', args=[self.course.slug, self.locked.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cannot_complete_lesson_from_another_course(self):
        enrollment = services.enroll(self.student, self.course, Enrollment.Source.ADMIN)
        other = make_course().lessons().first()
        with self.assertRaises(services.EnrollmentError):
            services.mark_lesson_complete(enrollment, other)

    def test_draft_course_hidden_from_students(self):
        draft = make_course(status='draft')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse('courses:list')), draft.title)

    def test_duplicate_enrolment_rejected(self):
        services.enroll(self.student, self.course, Enrollment.Source.ADMIN)
        with self.assertRaises(services.EnrollmentError):
            services.enroll(self.student, self.course, Enrollment.Source.ADMIN)
        self.assertEqual(Enrollment.objects.count(), 1)


class ProgressAndCertificateTests(TestCase):
    def setUp(self):
        self.student = make_user()

    def test_progress_is_percentage_of_required_lessons(self):
        course = make_course(lessons=10)
        enrollment = services.enroll(self.student, course, Enrollment.Source.ADMIN)
        for lesson in list(course.lessons())[:8]:
            services.mark_lesson_complete(enrollment, lesson)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 80)
        self.assertIsNone(enrollment.completed_at)

    def test_optional_lessons_do_not_count(self):
        course = make_course(lessons=4)
        lessons = list(course.lessons())
        Lesson.objects.filter(pk=lessons[3].pk).update(is_required=False)
        enrollment = services.enroll(self.student, course, Enrollment.Source.ADMIN)
        for lesson in lessons[:3]:
            services.mark_lesson_complete(enrollment, lesson)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 100)
        self.assertTrue(Certificate.objects.filter(enrollment=enrollment).exists())

    def test_certificate_requires_passing_required_quiz(self):
        course = make_course(lessons=2)
        quiz, question, right, wrong = make_quiz(course)
        enrollment = services.enroll(self.student, course, Enrollment.Source.ADMIN)
        for lesson in course.lessons():
            services.mark_lesson_complete(enrollment, lesson)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 66)  # 2 of 3 items
        self.assertFalse(Certificate.objects.exists())
        self.assertIsNone(services.issue_certificate(enrollment))

        attempt = quiz_services.start_attempt(quiz, self.student)
        from django.http import QueryDict
        data = QueryDict(mutable=True)
        data.setlist(f'q{question.pk}', [str(right.pk)])
        quiz_services.submit_attempt(attempt.pk, self.student, data)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 100)
        cert = Certificate.objects.get(enrollment=enrollment)
        self.assertEqual(services.issue_certificate(enrollment).pk, cert.pk)  # no duplicates
        self.assertEqual(Certificate.objects.count(), 1)

    def test_sequential_course_locks_later_lessons(self):
        course = make_course(lessons=3, sequential_progression=True)
        lessons = list(course.lessons())
        enrollment = services.enroll(self.student, course, Enrollment.Source.ADMIN)
        with self.assertRaises(services.EnrollmentError):
            services.mark_lesson_complete(enrollment, lessons[2])

    def test_certificate_download_and_public_verification(self):
        course = make_course(lessons=1)
        enrollment = services.enroll(self.student, course, Enrollment.Source.ADMIN)
        services.mark_lesson_complete(enrollment, course.lessons().first())
        cert = Certificate.objects.get()
        self.client.force_login(self.student)
        response = self.client.get(reverse('learning:certificate_pdf', args=[cert.certificate_number]))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.client.logout()
        self.assertContains(self.client.get(cert.get_absolute_url()), 'Valid certificate')
        other = make_user()
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('learning:certificate_pdf', args=[cert.certificate_number])).status_code, 403)
