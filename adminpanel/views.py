from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts import services as account_services
from accounts.models import InstructorApplication, User
from commerce import services as commerce_services
from commerce.models import InstructorEarning, Order, PaymentTransaction
from core.audit import log_action
from core.models import Announcement, AuditLog, PlatformSettings, Report
from core.permissions import admin_required
from courses import services as course_services
from courses.models import Category, Course, Lesson, ModerationDecision, Review, Tag
from learning import services as learning
from learning.models import Enrollment
from notifications.services import notify

from .forms import (AnnouncementForm, CategoryForm, GrantEnrollmentForm, ModerationForm, PlatformSettingsForm,
                    ReasonForm, TagForm)


def _page(request, qs, per_page=25):
    return Paginator(qs, per_page).get_page(request.GET.get('page'))


def _back(request, default, *args):
    target = request.POST.get('next', '')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(default, *args)


def _querystring(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


@admin_required
def dashboard(request):
    paid = Order.objects.filter(status=Order.Status.PAID)
    month_ago = timezone.now() - timedelta(days=30)
    return render(request, 'adminpanel/dashboard.html', {
        'section': 'dashboard',
        'stats': {
            'users': User.objects.count(),
            'students': User.objects.filter(role=User.Role.STUDENT).count(),
            'active_students': Enrollment.objects.filter(status=Enrollment.Status.ACTIVE,
                                                         last_accessed_at__gte=month_ago)
                                                 .values('student').distinct().count(),
            'instructors': User.objects.filter(role=User.Role.INSTRUCTOR).count(),
            'published': Course.objects.filter(status=Course.Status.PUBLISHED).count(),
            'pending': Course.objects.filter(status=Course.Status.SUBMITTED).count(),
            'enrollments': Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).count(),
            'sales': paid.aggregate(t=Sum('total'))['t'] or Decimal(0),
            'orders': paid.count(),
            'suspended': User.objects.filter(is_active=False).count(),
        },
        'queues': {
            'courses': Course.objects.filter(status=Course.Status.SUBMITTED).select_related('instructor')
                                     .order_by('submitted_at')[:5],
            'applications': InstructorApplication.objects.filter(status=InstructorApplication.Status.PENDING)
                                                         .select_related('user')[:5],
            'reports': Report.objects.filter(status=Report.Status.OPEN).select_related('reporter')[:5],
        },
        'counts': {
            'applications': InstructorApplication.objects.filter(status=InstructorApplication.Status.PENDING).count(),
            'reports': Report.objects.filter(status=Report.Status.OPEN).count(),
        },
        'recent_transactions': PaymentTransaction.objects.select_related('order__student')[:6],
        'recent_audit': AuditLog.objects.select_related('actor')[:6],
    })


@admin_required
def analytics(request):
    since = (timezone.now() - timedelta(days=365)).replace(day=1)
    monthly = list(Order.objects.filter(status=Order.Status.PAID, paid_at__gte=since)
                   .annotate(month=TruncMonth('paid_at')).values('month')
                   .annotate(revenue=Sum('total'), orders=Count('pk')).order_by('month'))
    enroll_monthly = {row['month']: row['n'] for row in Enrollment.objects.filter(enrolled_at__gte=since)
                      .annotate(month=TruncMonth('enrolled_at')).values('month').annotate(n=Count('pk'))}
    peak = max((m['revenue'] for m in monthly), default=0) or 1
    for m in monthly:
        m['bar'] = int(m['revenue'] * 100 / peak)
        m['enrollments'] = enroll_monthly.get(m['month'], 0)

    earnings = InstructorEarning.objects.filter(status=InstructorEarning.Status.RECORDED).aggregate(
        gross=Sum('gross_amount'), fee=Sum('platform_fee'), net=Sum('net_amount'))
    categories = (Category.objects.annotate(
        courses_n=Count('courses', filter=Q(courses__status=Course.Status.PUBLISHED), distinct=True),
        enrollments_n=Count('courses__enrollments', filter=Q(courses__enrollments__status='active'), distinct=True))
        .order_by('-enrollments_n'))
    cat_peak = max((c.enrollments_n for c in categories), default=0) or 1
    txn_status = dict(PaymentTransaction.objects.values_list('status').annotate(n=Count('pk')).order_by())
    return render(request, 'adminpanel/analytics.html', {
        'section': 'analytics',
        'monthly': monthly,
        'earnings': earnings,
        'categories': categories, 'cat_peak': cat_peak,
        'top_courses': Course.objects.published().with_stats().select_related('instructor')
                             .order_by('-students_count')[:10],
        'txn_status': [(label, txn_status.get(value, 0)) for value, label in PaymentTransaction.Status.choices],
        'completion': Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).aggregate(
            total=Count('pk'), done=Count('pk', filter=Q(completed_at__isnull=False))),
        'role_counts': dict(User.objects.values_list('role').annotate(n=Count('pk')).order_by()),
    })


@admin_required
def users(request):
    qs = User.objects.annotate(enroll_n=Count('enrollments', distinct=True),
                               course_n=Count('courses_taught', distinct=True)).order_by('-date_joined')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q))
    role = request.GET.get('role')
    if role in User.Role.values:
        qs = qs.filter(role=role)
    status = request.GET.get('status')
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'suspended':
        qs = qs.filter(is_active=False)
    return render(request, 'adminpanel/users.html', {
        'section': 'users', 'page_obj': _page(request, qs), 'q': q, 'role': role, 'status': status,
        'roles': User.Role.choices, 'querystring': _querystring(request)})


@admin_required
def user_detail(request, pk):
    member = get_object_or_404(User, pk=pk)
    return render(request, 'adminpanel/user_detail.html', {
        'section': 'users', 'member': member,
        'enrollments': member.enrollments.select_related('course'),
        'courses': Course.objects.filter(instructor=member).with_stats(),
        'orders': member.orders.all()[:10],
        'applications': member.instructor_applications.all(),
        'reports': Report.objects.filter(reported_user=member),
        'audit': AuditLog.objects.filter(target_type='user', target_id=str(member.pk))[:10],
        'grant_form': GrantEnrollmentForm(), 'reason_form': ReasonForm(), 'roles': User.Role.choices,
    })


@admin_required
@require_POST
def user_suspend(request, pk):
    member = get_object_or_404(User, pk=pk)
    suspend = request.POST.get('action') == 'suspend'
    try:
        account_services.set_suspended(member, request.user, suspend, request.POST.get('reason', ''), request)
        messages.success(request, f'{member.display_name} has been {"suspended" if suspend else "reactivated"}.')
    except account_services.AccountError as exc:
        messages.error(request, str(exc))
    return redirect('adminpanel:user_detail', member.pk)


@admin_required
@require_POST
def user_role(request, pk):
    member = get_object_or_404(User, pk=pk)
    try:
        account_services.change_role(member, request.user, request.POST.get('role'), request)
        messages.success(request, f'Role updated to {member.get_role_display()}.')
    except account_services.AccountError as exc:
        messages.error(request, str(exc))
    return redirect('adminpanel:user_detail', member.pk)


@admin_required
@require_POST
def user_grant(request, pk):
    member = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    form = GrantEnrollmentForm(request.POST)
    if form.is_valid():
        course = form.cleaned_data['course']
        try:
            enrollment = learning.enroll(member, course, Enrollment.Source.ADMIN)
        except learning.EnrollmentError as exc:
            messages.error(request, str(exc))
        else:
            log_action(request.user, 'enrollment.granted', enrollment,
                       {'student': member.username, 'course': course.title, 'reason': form.cleaned_data['reason']},
                       request)
            notify(member, f'You have been given access to {course.title}', url=f'/learn/{course.slug}/')
            messages.success(request, f'Access to "{course.title}" granted.')
    else:
        messages.error(request, 'Choose a course and give a reason.')
    return redirect('adminpanel:user_detail', member.pk)


@admin_required
def applications(request):
    status = request.GET.get('status', 'pending')
    qs = InstructorApplication.objects.select_related('user', 'reviewed_by')
    if status in InstructorApplication.Status.values:
        qs = qs.filter(status=status)
    return render(request, 'adminpanel/applications.html', {
        'section': 'applications', 'page_obj': _page(request, qs), 'status': status,
        'statuses': InstructorApplication.Status.choices,
        'require_approval': PlatformSettings.load().require_instructor_approval})


@admin_required
@require_POST
def application_decide(request, pk):
    application = get_object_or_404(InstructorApplication, pk=pk)
    approve = request.POST.get('decision') == 'approve'
    try:
        account_services.decide_application(application, request.user, approve,
                                            request.POST.get('note', '').strip(), request)
        messages.success(request, f'Application {"approved" if approve else "rejected"}.')
    except account_services.AccountError as exc:
        messages.error(request, str(exc))
    return redirect('adminpanel:applications')


@admin_required
def courses(request):
    status = request.GET.get('status', Course.Status.SUBMITTED)
    qs = Course.objects.with_stats().select_related('instructor', 'category')
    if status in Course.Status.values:
        qs = qs.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(instructor__username__icontains=q)
                       | Q(instructor__first_name__icontains=q) | Q(instructor__last_name__icontains=q))
    qs = qs.order_by('submitted_at' if status == Course.Status.SUBMITTED else '-updated_at')
    counts = dict(Course.objects.values_list('status').annotate(n=Count('pk')).order_by())
    return render(request, 'adminpanel/courses.html', {
        'section': 'courses', 'page_obj': _page(request, qs), 'status': status, 'q': q,
        'statuses': [(v, label, counts.get(v, 0)) for v, label in Course.Status.choices],
        'querystring': _querystring(request)})


@admin_required
def course_review(request, pk):
    course = get_object_or_404(Course.objects.select_related('instructor', 'category'), pk=pk)
    sections = course.sections.prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order', 'id').prefetch_related('resources')))
    instructor = course.instructor
    return render(request, 'adminpanel/course_review.html', {
        'section': 'courses', 'course': course, 'sections': sections,
        'quizzes': course.quizzes.prefetch_related('questions__options'),
        'timeline': course.moderation_decisions.select_related('actor'),
        'problems': course_services.readiness_problems(course),
        'actions': [(a, ModerationDecision.Action(a).label) for a in course_services.admin_available_actions(course)],
        'form': ModerationForm(),
        'stats': Course.objects.filter(pk=course.pk).with_stats().values('students_count', 'rating_avg',
                                                                          'rating_count').get(),
        'instructor_courses': Course.objects.filter(instructor=instructor).exclude(pk=course.pk),
        'instructor_application': instructor.instructor_applications.filter(
            status=InstructorApplication.Status.APPROVED).first(),
        'reports': course.reports.select_related('reporter'),
    })


@admin_required
@require_POST
def course_moderate(request, pk):
    course = get_object_or_404(Course, pk=pk)
    form = ModerationForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a valid moderation action.')
        return redirect('adminpanel:course_review', course.pk)
    try:
        decision = course_services.moderate(course, request.user, form.cleaned_data['action'],
                                            form.cleaned_data['reason'], request)
        messages.success(request, f'Decision recorded: {decision.get_action_display()}.')
    except course_services.ModerationError as exc:
        messages.error(request, str(exc))
    return redirect('adminpanel:course_review', course.pk)


@admin_required
@require_POST
def course_feature(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if not course.is_published and not course.is_featured:
        messages.error(request, 'Only published courses can be featured.')
    else:
        course.is_featured = not course.is_featured
        course.save(update_fields=['is_featured'])
        log_action(request.user, 'course.featured' if course.is_featured else 'course.unfeatured', course,
                   request=request)
        messages.success(request, 'Course featured on the home page.' if course.is_featured
                         else 'Course removed from featured.')
    return _back(request, 'adminpanel:course_review', course.pk)


@admin_required
def reviews(request):
    qs = Review.objects.select_related('course', 'student').annotate(
        report_n=Count('reports', filter=Q(reports__status=Report.Status.OPEN)))
    view = request.GET.get('view', 'all')
    if view == 'hidden':
        qs = qs.filter(is_hidden=True)
    elif view == 'reported':
        qs = qs.filter(report_n__gt=0)
    elif view == 'low':
        qs = qs.filter(rating__lte=2)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(comment__icontains=q) | Q(course__title__icontains=q) | Q(student__username__icontains=q))
    return render(request, 'adminpanel/reviews.html', {
        'section': 'reviews', 'page_obj': _page(request, qs), 'view': view, 'q': q,
        'querystring': _querystring(request)})


@admin_required
@require_POST
def review_toggle(request, pk):
    review = get_object_or_404(Review, pk=pk)
    hide = not review.is_hidden
    reason = request.POST.get('reason', '').strip()
    if hide and not reason:
        messages.error(request, 'Give a reason for hiding this review.')
        return _back(request, 'adminpanel:reviews')
    review.is_hidden = hide
    review.hidden_reason = reason if hide else ''
    review.save(update_fields=['is_hidden', 'hidden_reason'])
    log_action(request.user, 'review.hidden' if hide else 'review.restored', review, {'reason': reason}, request)
    if hide:
        notify(review.student, f'Your review of {review.course.title} was hidden', reason)
    messages.success(request, 'Review hidden.' if hide else 'Review restored.')
    return _back(request, 'adminpanel:reviews')


@admin_required
def reports(request):
    status = request.GET.get('status', Report.Status.OPEN)
    qs = Report.objects.select_related('reporter', 'course', 'review__course', 'reported_user', 'resolved_by')
    if status in Report.Status.values:
        qs = qs.filter(status=status)
    target = request.GET.get('target')
    if target in Report.TargetType.values:
        qs = qs.filter(target_type=target)
    return render(request, 'adminpanel/reports.html', {
        'section': 'reports', 'page_obj': _page(request, qs), 'status': status, 'target': target,
        'statuses': Report.Status.choices, 'targets': Report.TargetType.choices,
        'querystring': _querystring(request)})


@admin_required
@require_POST
def report_resolve(request, pk):
    report = get_object_or_404(Report, pk=pk, status=Report.Status.OPEN)
    decision = request.POST.get('decision')
    if decision not in (Report.Status.RESOLVED, Report.Status.DISMISSED):
        messages.error(request, 'Choose resolve or dismiss.')
        return redirect('adminpanel:reports')
    report.status = decision
    report.resolution_note = request.POST.get('note', '').strip()
    report.resolved_by = request.user
    report.resolved_at = timezone.now()
    report.save()
    log_action(request.user, f'report.{decision}', report, {'note': report.resolution_note}, request)
    notify(report.reporter, 'Your report has been reviewed',
           f'Outcome: {report.get_status_display()}. {report.resolution_note}')
    messages.success(request, f'Report {report.get_status_display().lower()}.')
    return redirect('adminpanel:reports')


@admin_required
def transactions(request):
    qs = PaymentTransaction.objects.select_related('order__student')
    status = request.GET.get('status')
    if status in PaymentTransaction.Status.values:
        qs = qs.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(transaction_id__icontains=q) | Q(order__order_number__icontains=q)
                       | Q(order__student__username__icontains=q) | Q(order__student__email__icontains=q))
    totals = qs.aggregate(amount=Sum('amount'))
    return render(request, 'adminpanel/transactions.html', {
        'section': 'transactions', 'page_obj': _page(request, qs), 'status': status, 'q': q,
        'statuses': PaymentTransaction.Status.choices, 'totals': totals,
        'querystring': _querystring(request)})


@admin_required
def order_detail(request, order_number):
    order = get_object_or_404(Order.objects.select_related('student'), order_number=order_number)
    return render(request, 'adminpanel/order_detail.html', {
        'section': 'transactions', 'order': order,
        'items': order.items.select_related('course', 'instructor').prefetch_related('earning'),
        'transactions': order.transactions.all(), 'form': ReasonForm()})


@admin_required
@require_POST
def order_refund(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    form = ReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'A refund reason is required.')
        return redirect('adminpanel:order_detail', order.order_number)
    try:
        commerce_services.refund_order(order, request.user, form.cleaned_data['reason'])
        log_action(request.user, 'order.refunded', order, {'reason': form.cleaned_data['reason'],
                                                           'amount': str(order.total)}, request)
        messages.success(request, 'Simulated refund issued; course access revoked.')
    except commerce_services.CheckoutError as exc:
        messages.error(request, str(exc))
    return redirect('adminpanel:order_detail', order.order_number)


@admin_required
def categories(request, pk=None):
    instance = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        log_action(request.user, 'category.updated' if instance else 'category.created', category, request=request)
        messages.success(request, f'Category "{category.name}" saved.')
        return redirect('adminpanel:categories')
    return render(request, 'adminpanel/categories.html', {
        'section': 'categories', 'form': form, 'editing': instance,
        'categories': Category.objects.annotate(course_n=Count('courses')),
        'tags': Tag.objects.annotate(course_n=Count('courses')), 'tag_form': TagForm()})


@admin_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.courses.exists():
        messages.error(request, 'This category has courses. Deactivate it instead.')
    else:
        log_action(request.user, 'category.deleted', category, request=request)
        category.delete()
        messages.success(request, 'Category deleted.')
    return redirect('adminpanel:categories')


@admin_required
@require_POST
def tag_create(request):
    form = TagForm(request.POST)
    if form.is_valid():
        tag = form.save()
        log_action(request.user, 'tag.created', tag, request=request)
        messages.success(request, f'Tag "{tag.name}" added.')
    else:
        messages.error(request, ' '.join(form.errors.get('name', ['Invalid tag.'])))
    return redirect('adminpanel:categories')


@admin_required
@require_POST
def tag_delete(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    log_action(request.user, 'tag.deleted', tag, request=request)
    tag.delete()
    messages.success(request, 'Tag deleted.')
    return redirect('adminpanel:categories')


@admin_required
def announcements(request, pk=None):
    instance = get_object_or_404(Announcement, pk=pk) if pk else None
    form = AnnouncementForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        announcement = form.save(commit=False)
        if not instance:
            announcement.created_by = request.user
        announcement.save()
        log_action(request.user, 'announcement.saved', announcement, request=request)
        messages.success(request, 'Announcement saved.')
        return redirect('adminpanel:announcements')
    return render(request, 'adminpanel/announcements.html', {
        'section': 'announcements', 'form': form, 'editing': instance,
        'announcements': Announcement.objects.select_related('created_by')})


@admin_required
@require_POST
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    log_action(request.user, 'announcement.deleted', announcement, request=request)
    announcement.delete()
    messages.success(request, 'Announcement deleted.')
    return redirect('adminpanel:announcements')


@admin_required
def platform_settings(request):
    settings_obj = PlatformSettings.load()
    form = PlatformSettingsForm(request.POST or None, instance=settings_obj)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            log_action(request.user, 'settings.updated', settings_obj,
                       {'changed': form.changed_data}, request)
            messages.success(request, 'Platform settings saved.')
            return redirect('adminpanel:settings')
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'adminpanel/settings.html', {'section': 'settings', 'form': form})


@admin_required
def audit_logs(request):
    qs = AuditLog.objects.select_related('actor')
    action = request.GET.get('action', '').strip()
    if action:
        qs = qs.filter(action__startswith=action)
    actor = request.GET.get('actor', '').strip()
    if actor:
        qs = qs.filter(actor__username__icontains=actor)
    prefixes = sorted({a.split('.')[0] for a in AuditLog.objects.values_list('action', flat=True).distinct()})
    return render(request, 'adminpanel/audit.html', {
        'section': 'audit', 'page_obj': _page(request, qs, 40), 'action': action, 'actor': actor,
        'prefixes': prefixes, 'querystring': _querystring(request)})
