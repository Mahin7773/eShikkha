from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.testing import make_course, make_user
from learning.models import Enrollment

from . import services
from .models import InstructorEarning, Order, PaymentTransaction


class SimulatedPaymentTests(TestCase):
    def setUp(self):
        self.student = make_user()
        self.course = make_course(price='40.00', discount_price=Decimal('25.00'))

    def test_order_uses_server_side_discounted_price(self):
        order = services.create_order(self.student, [self.course.pk])
        self.assertEqual(order.subtotal, Decimal('40.00'))
        self.assertEqual(order.discount_total, Decimal('15.00'))
        self.assertEqual(order.total, Decimal('25.00'))

    def test_client_supplied_price_is_ignored(self):
        self.client.force_login(self.student)
        self.client.post(reverse('commerce:buy_now', args=[self.course.pk]), {'price': '0.01', 'total': '0'})
        order = Order.objects.get(student=self.student)
        self.assertEqual(order.total, Decimal('25.00'))

    def test_successful_payment_enrols_and_records_earning(self):
        order = services.create_order(self.student, [self.course.pk])
        txn = services.process_payment(order.order_number, self.student, 'success')
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESSFUL)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=self.course, status='active').exists())
        earning = InstructorEarning.objects.get(order_item__order=order)
        self.assertEqual(earning.gross_amount, Decimal('25.00'))
        self.assertEqual(earning.platform_fee + earning.net_amount, earning.gross_amount)

    def test_replayed_success_is_idempotent(self):
        order = services.create_order(self.student, [self.course.pk])
        first = services.process_payment(order.order_number, self.student, 'success')
        second = services.process_payment(order.order_number, self.student, 'success')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 1)
        self.assertEqual(Enrollment.objects.filter(student=self.student, course=self.course).count(), 1)
        self.assertEqual(InstructorEarning.objects.count(), 1)

    def test_declined_payment_grants_no_access_and_can_be_retried(self):
        order = services.create_order(self.student, [self.course.pk])
        txn = services.process_payment(order.order_number, self.student, 'decline')
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)
        self.assertFalse(Enrollment.objects.filter(student=self.student).exists())
        services.process_payment(order.order_number, self.student, 'success')
        self.assertTrue(Enrollment.objects.filter(student=self.student).exists())

    def test_cancelled_order_cannot_be_paid(self):
        order = services.create_order(self.student, [self.course.pk])
        services.process_payment(order.order_number, self.student, 'cancel')
        with self.assertRaises(services.CheckoutError):
            services.process_payment(order.order_number, self.student, 'success')
        self.assertFalse(Enrollment.objects.exists())

    def test_unknown_outcome_rejected(self):
        order = services.create_order(self.student, [self.course.pk])
        with self.assertRaises(services.CheckoutError):
            services.process_payment(order.order_number, self.student, 'free-money')

    def test_cannot_buy_owned_unpublished_or_own_course(self):
        services.process_payment(services.create_order(self.student, [self.course.pk]).order_number,
                                 self.student, 'success')
        with self.assertRaises(services.CheckoutError):
            services.create_order(self.student, [self.course.pk])
        draft = make_course(status='draft')
        with self.assertRaises(services.CheckoutError):
            services.create_order(self.student, [draft.pk])
        with self.assertRaises(services.CheckoutError):
            services.create_order(self.course.instructor, [self.course.pk])

    def test_other_student_cannot_pay_someone_elses_order(self):
        order = services.create_order(self.student, [self.course.pk])
        intruder = make_user()
        self.client.force_login(intruder)
        response = self.client.post(reverse('commerce:sandbox', args=[order.order_number]), {'outcome': 'success'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Enrollment.objects.exists())

    def test_refund_revokes_access_and_reverses_earnings(self):
        admin = make_user(role='admin')
        order = services.create_order(self.student, [self.course.pk])
        services.process_payment(order.order_number, self.student, 'success')
        services.refund_order(order, admin, 'Requested by student')
        self.assertEqual(Enrollment.objects.get().status, Enrollment.Status.REFUNDED)
        self.assertEqual(InstructorEarning.objects.get().status, InstructorEarning.Status.REVERSED)
        self.assertEqual(PaymentTransaction.objects.get().status, PaymentTransaction.Status.REFUNDED)
