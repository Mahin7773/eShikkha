import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import PlatformSettings
from courses.models import Course
from learning import services as learning
from learning.models import Enrollment
from notifications.models import Notification
from notifications.services import notify

from .models import Cart, CartItem, InstructorEarning, Order, OrderItem, PaymentTransaction

CENT = Decimal('0.01')


class CheckoutError(Exception):
    pass


def _purchase_problem(user, course):
    """Return why `user` cannot buy `course`, or None."""
    if course.status != Course.Status.PUBLISHED:
        return f'"{course.title}" is not currently available.'
    if course.instructor_id == user.id:
        return 'You cannot purchase your own course.'
    if Enrollment.objects.filter(student=user, course=course, status=Enrollment.Status.ACTIVE).exists():
        return f'You already own "{course.title}".'
    return None


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def add_to_cart(user, course):
    if problem := _purchase_problem(user, course):
        raise CheckoutError(problem)
    if course.is_free:
        raise CheckoutError('Free courses do not need checkout. Use "Enroll for free" instead.')
    _, created = CartItem.objects.get_or_create(cart=get_cart(user), course=course)
    return created


def remove_from_cart(user, course_id):
    CartItem.objects.filter(cart__user=user, course_id=course_id).delete()


def cart_courses(user):
    return [item.course for item in get_cart(user).items.select_related('course__instructor')]


def price_summary(courses):
    subtotal = sum((c.price for c in courses), Decimal(0))
    total = sum((c.current_price for c in courses), Decimal(0))
    return {'subtotal': subtotal, 'discount': subtotal - total, 'total': total}


def _order_number():
    return f'ORD-{timezone.now():%Y%m%d}-{secrets.token_hex(4).upper()}'


def _transaction_id():
    return f'TXN-{secrets.token_hex(8).upper()}'


@transaction.atomic
def create_order(user, course_ids):
    course_ids = list(dict.fromkeys(int(c) for c in course_ids))
    if not course_ids:
        raise CheckoutError('Your cart is empty.')
    courses = list(Course.objects.filter(pk__in=course_ids).select_related('instructor'))
    if len(courses) != len(course_ids):
        raise CheckoutError('One of the selected courses no longer exists.')
    for course in courses:
        if problem := _purchase_problem(user, course):
            raise CheckoutError(problem)
        if course.is_free:
            raise CheckoutError(f'"{course.title}" is free. Enrol directly from the course page.')

    totals = price_summary(courses)
    order = Order.objects.create(order_number=_order_number(), student=user,
                                 subtotal=totals['subtotal'], discount_total=totals['discount'],
                                 total=totals['total'])
    OrderItem.objects.bulk_create([
        OrderItem(order=order, course=c, instructor=c.instructor, list_price=c.price,
                  discount_amount=c.discount_amount, price_paid=c.current_price)
        for c in courses
    ])
    return order


@transaction.atomic
def cancel_order(order, user):
    order = Order.objects.select_for_update().get(pk=order.pk, student=user)
    if not order.is_payable:
        raise CheckoutError('This order can no longer be cancelled.')
    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status', 'updated_at'])
    return order


def process_payment(order_number, user, outcome):
    """Fake gateway. Paying an already paid order just returns the old transaction."""
    if outcome not in PaymentTransaction.Outcome.values:
        raise CheckoutError('Unknown payment outcome.')

    with transaction.atomic():
        order = Order.objects.select_for_update().get(order_number=order_number, student=user)
        if order.status == Order.Status.PAID:
            return order.transactions.get(status=PaymentTransaction.Status.SUCCESSFUL)
        if not order.is_payable:
            raise CheckoutError(f'This order is {order.get_status_display().lower()} and cannot be paid.')

        txn = PaymentTransaction.objects.create(order=order, transaction_id=_transaction_id(),
                                                amount=order.total, simulated_outcome=outcome)
        items = list(order.items.select_related('course__instructor'))

        if outcome == PaymentTransaction.Outcome.CANCEL:
            txn.status = PaymentTransaction.Status.CANCELLED
            txn.message = 'Payment was cancelled at the simulated gateway.'
            order.status = Order.Status.CANCELLED
        elif outcome == PaymentTransaction.Outcome.DECLINE:
            txn.status = PaymentTransaction.Status.FAILED
            txn.message = 'Simulated card declined: insufficient funds.'
            order.status = Order.Status.FAILED
        else:
            problems = [p for p in (_purchase_problem(user, i.course) for i in items) if p]
            if problems:
                txn.status = PaymentTransaction.Status.FAILED
                txn.message = f'Payment not taken: {problems[0]}'[:200]
                order.status = Order.Status.FAILED
            else:
                txn.status = PaymentTransaction.Status.SUCCESSFUL
                txn.message = 'Simulated payment approved.'
                order.status = Order.Status.PAID
                order.paid_at = timezone.now()

        txn.processed_at = timezone.now()
        try:
            txn.save()
        except IntegrityError:
            raise CheckoutError('This order has already been paid.')
        order.save()

        if txn.status == PaymentTransaction.Status.SUCCESSFUL:
            _fulfil(order, items)

    if txn.status == PaymentTransaction.Status.SUCCESSFUL:
        notify(user, f'Payment received for order {order.order_number}',
               f'You now have access to {len(items)} course(s).', url='/learn/', kind=Notification.Kind.PAYMENT)
    return txn


def _fulfil(order, items):
    fee_percent = PlatformSettings.load().platform_fee_percent
    for item in items:
        learning.enroll(order.student, item.course, Enrollment.Source.PURCHASE, order=order)
        fee = (item.price_paid * fee_percent / 100).quantize(CENT, ROUND_HALF_UP)
        InstructorEarning.objects.create(
            order_item=item, instructor=item.instructor, course=item.course,
            gross_amount=item.price_paid, fee_percent=fee_percent,
            platform_fee=fee, net_amount=item.price_paid - fee)
    CartItem.objects.filter(cart__user=order.student, course__in=[i.course for i in items]).delete()


@transaction.atomic
def refund_order(order, admin, reason):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.PAID:
        raise CheckoutError('Only paid orders can be refunded.')
    txn = order.transactions.get(status=PaymentTransaction.Status.SUCCESSFUL)
    txn.status = PaymentTransaction.Status.REFUNDED
    txn.message = f'Refunded by administrator: {reason}'[:200]
    txn.save(update_fields=['status', 'message'])
    order.status = Order.Status.REFUNDED
    order.save(update_fields=['status', 'updated_at'])

    for enrollment in order.enrollments.filter(status=Enrollment.Status.ACTIVE):
        enrollment.status = Enrollment.Status.REFUNDED
        enrollment.save(update_fields=['status'])
        cert = getattr(enrollment, 'certificate', None) if hasattr(enrollment, 'certificate') else None
        if cert and not cert.is_revoked:
            cert.is_revoked = True
            cert.revoked_reason = 'Enrolment refunded'
            cert.save(update_fields=['is_revoked', 'revoked_reason'])
    InstructorEarning.objects.filter(order_item__order=order).update(status=InstructorEarning.Status.REVERSED)
    notify(order.student, f'Order {order.order_number} refunded',
           'A simulated refund was issued and course access was removed.',
           url=order.get_absolute_url(), kind=Notification.Kind.PAYMENT)
    return order
