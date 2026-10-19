from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog, PlatformSettings
from core.testing import make_course, make_user
from learning import services as learning
from learning.models import Enrollment

from . import services
from .models import Course, ModerationDecision


class ModerationWorkflowTests(TestCase):
    def setUp(self):
        self.admin = make_user(role='admin')
        self.course = make_course(status=Course.Status.DRAFT)
        self.instructor = self.course.instructor

    def test_submission_requires_approval_before_publication(self):
        services.submit_for_review(self.course, self.instructor)
        self.assertEqual(self.course.status, Course.Status.SUBMITTED)
        self.assertEqual(self.client.get(self.course.get_absolute_url()).status_code, 404)
        services.moderate(self.course, self.admin, 'approved')
        self.assertEqual(self.course.status, Course.Status.PUBLISHED)
        self.assertEqual(self.client.get(self.course.get_absolute_url()).status_code, 200)
        decision = self.course.moderation_decisions.get(action='approved')
        self.assertEqual(decision.actor, self.admin)
        self.assertTrue(AuditLog.objects.filter(action='course.approved').exists())

    def test_auto_publish_when_approval_disabled(self):
        settings = PlatformSettings.load()
        settings.require_course_approval = False
        settings.save()
        services.submit_for_review(self.course, self.instructor)
        self.assertEqual(self.course.status, Course.Status.PUBLISHED)

    def test_rejection_requires_reason(self):
        services.submit_for_review(self.course, self.instructor)
        with self.assertRaises(services.ModerationError):
            services.moderate(self.course, self.admin, 'rejected', '')
        services.moderate(self.course, self.admin, 'rejected', 'Audio is inaudible.')
        self.assertEqual(self.course.latest_feedback.reason, 'Audio is inaudible.')

    def test_cannot_submit_empty_course_or_someone_elses(self):
        empty = make_course(status=Course.Status.DRAFT, lessons=0)
        with self.assertRaises(services.ModerationError):
            services.submit_for_review(empty, empty.instructor)
        with self.assertRaises(services.ModerationError):
            services.submit_for_review(self.course, make_user(role='instructor'))

    def test_invalid_transition_rejected(self):
        with self.assertRaises(services.ModerationError):
            services.moderate(self.course, self.admin, 'approved')  # still a draft

    def test_instructor_cannot_moderate(self):
        services.submit_for_review(self.course, self.instructor)
        with self.assertRaises(services.ModerationError):
            services.moderate(self.course, self.instructor, 'approved')
        self.assertFalse(ModerationDecision.objects.filter(action='approved').exists())


class StudioOwnershipTests(TestCase):
    def test_instructor_cannot_open_another_instructors_course(self):
        course = make_course()
        intruder = make_user(role='instructor')
        self.client.force_login(intruder)
        for name in ('studio:course', 'studio:course_edit', 'studio:students', 'studio:curriculum'):
            self.assertEqual(self.client.get(reverse(name, args=[course.pk])).status_code, 404, name)

    def test_students_cannot_open_studio_or_admin(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse('studio:dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('adminpanel:dashboard')).status_code, 403)


class ReviewRuleTests(TestCase):
    def test_review_requires_enrolment_and_minimum_progress(self):
        course = make_course(lessons=10)
        student = make_user()
        with self.assertRaises(services.ModerationError):
            services.save_review(student, course, 5, 'Great')
        enrollment = learning.enroll(student, course, Enrollment.Source.ADMIN)
        with self.assertRaises(services.ModerationError):
            services.save_review(student, course, 5, 'Great')  # 0% < 10%
        learning.mark_lesson_complete(enrollment, course.lessons().first())
        services.save_review(student, course, 4, 'Good')
        services.save_review(student, course, 5, 'Even better')
        self.assertEqual(course.reviews.get().rating, 5)
