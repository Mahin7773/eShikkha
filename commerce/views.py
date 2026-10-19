from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.permissions import student_required
from courses.models import Course
from learning import services as learning
from learning.models import Enrollment

from . import services
from .models import Order, PaymentTransaction


@student_required
def cart(request):
    courses = services.cart_courses(request.user)
    return render(request, 'commerce/cart.html', {
        'courses': courses, 'summary': services.price_summary(courses)})


@student_required
@require_POST
def add_to_cart(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    try:
        created = services.add_to_cart(request.user, course)
    except services.CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect(course.get_absolute_url())
    messages.success(request, f'"{course.title}" added to your cart.' if created else 'Already in your cart.')
    return redirect('commerce:cart')


@student_required
@require_POST
def remove_from_cart(request, course_id):
    services.remove_from_cart(request.user, course_id)
    messages.success(request, 'Removed from cart.')
    return redirect('commerce:cart')


@student_required
@require_POST
def checkout(request):
    course_ids = [c.pk for c in services.cart_courses(request.user)]
    try:
        order = services.create_order(request.user, course_ids)
    except services.CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect('commerce:cart')
    return redirect('commerce:order_detail', order.order_number)


@student_required
@require_POST
def buy_now(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    try:
        order = services.create_order(request.user, [course.pk])
    except services.CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect(course.get_absolute_url())
    return redirect('commerce:order_detail', order.order_number)


@student_required
@require_POST
def enroll_free(request, course_id):
    course = get_object_or_404(Course, pk=course_id, status=Course.Status.PUBLISHED)
    if not course.is_free:
        messages.error(request, 'This course is not free.')
        return redirect(course.get_absolute_url())
    try:
        learning.enroll(request.user, course, Enrollment.Source.FREE)
    except learning.EnrollmentError as exc:
        messages.info(request, str(exc))
    else:
        messages.success(request, f'You are enrolled in "{course.title}". Happy learning!')
    return redirect('learning:resume', course.slug)


@student_required
def order_detail(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related('items__course', 'transactions'),
                              order_number=order_number, student=request.user)
    return render(request, 'commerce/order_detail.html', {
        'order': order, 'latest_txn': order.transactions.first()})


@student_required
def sandbox(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, student=request.user)
    if request.method == 'POST':
        outcome = request.POST.get('outcome', '')
        try:
            txn = services.process_payment(order.order_number, request.user, outcome)
        except services.CheckoutError as exc:
            messages.error(request, str(exc))
            return redirect('commerce:order_detail', order.order_number)
        if txn.status == PaymentTransaction.Status.SUCCESSFUL:
            messages.success(request, 'Payment successful. Your courses are ready!')
        elif txn.status == PaymentTransaction.Status.CANCELLED:
            messages.info(request, 'Payment cancelled. You have not been charged.')
        else:
            messages.error(request, txn.message)
        return redirect('commerce:order_detail', order.order_number)

    if not order.is_payable:
        return redirect('commerce:order_detail', order.order_number)
    return render(request, 'commerce/sandbox.html', {
        'order': order, 'outcomes': PaymentTransaction.Outcome.choices})


@student_required
@require_POST
def cancel_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, student=request.user)
    try:
        services.cancel_order(order, request.user)
        messages.info(request, f'Order {order.order_number} cancelled.')
    except services.CheckoutError as exc:
        messages.error(request, str(exc))
    return redirect('commerce:order_detail', order.order_number)


@student_required
def order_history(request):
    orders = request.user.orders.prefetch_related('items__course')
    page = Paginator(orders, 15).get_page(request.GET.get('page'))
    return render(request, 'commerce/orders.html', {'page_obj': page})
