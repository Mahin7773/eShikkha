from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog
from core.testing import make_user

from . import services
from .models import User


class AccountTests(TestCase):
    def test_register_and_login_with_email(self):
        response = self.client.post(reverse('accounts:register'), {
            'first_name': 'Ada', 'last_name': 'Lovelace', 'username': 'ada', 'email': 'ada@example.com',
            'password1': 'An4lytical-Engine', 'password2': 'An4lytical-Engine'})
        self.assertRedirects(response, reverse('courses:list'))
        self.client.logout()
        self.assertTrue(self.client.login(username='ada@example.com', password='An4lytical-Engine'))
        self.assertEqual(User.objects.get(username='ada').role, User.Role.STUDENT)

    def test_suspension_blocks_login_and_is_audited(self):
        admin = make_user(role='admin')
        student = make_user()
        services.set_suspended(student, admin, True, 'Spam')
        self.assertFalse(self.client.login(username=student.username, password='pw-Test-123'))
        response = self.client.post(reverse('accounts:login'), {'username': student.username, 'password': 'pw-Test-123'})
        self.assertContains(response, 'suspended')
        self.assertTrue(AuditLog.objects.filter(action='user.suspended', actor=admin).exists())

    def test_suspension_requires_reason_and_not_self(self):
        admin = make_user(role='admin')
        with self.assertRaises(services.AccountError):
            services.set_suspended(make_user(), admin, True, '')
        with self.assertRaises(services.AccountError):
            services.set_suspended(admin, admin, True, 'x')

    def test_instructor_application_approval_upgrades_role(self):
        admin = make_user(role='admin')
        student = make_user()
        self.client.force_login(student)
        self.client.post(reverse('accounts:apply_instructor'), {
            'headline': 'Engineer', 'expertise': 'Python', 'experience': 'Ten years'})
        application = student.instructor_applications.get()
        self.assertEqual(User.objects.get(pk=student.pk).role, User.Role.STUDENT)
        services.decide_application(application, admin, approve=True)
        self.assertEqual(User.objects.get(pk=student.pk).role, User.Role.INSTRUCTOR)
