from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from commerce.models import CartItem
from learning import services as learning

from . import selectors, services
from .forms import ReviewForm
from .models import Category, Course, Lesson


def course_list(request):
    qs, applied, sort = selectors.search_courses(request.GET)
    page = Paginator(qs, 12).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'courses/list.html', {
        'page_obj': page,
        'applied': applied,
        'sort': sort,
        'sort_options': {k: v[0] for k, v in selectors.SORT_OPTIONS.items()},
        'price_options': {k: v[0] for k, v in selectors.PRICE_FILTERS.items()},
        'rating_options': list(selectors.RATING_FILTERS),
        'levels': Course.Level.choices,
        'categories': Category.objects.filter(is_active=True),
        'querystring': params.urlencode(),
        'active_category': Category.objects.filter(slug__in=applied.get('category', [])).first(),
    })


def _visible_course(request, slug):
    course = get_object_or_404(Course.objects.select_related('instructor', 'category'), slug=slug)
    user = request.user
    if course.is_published or learning.can_access_content(user, course):
        return course
    raise Http404('Course not available')


def course_detail(request, slug):
    course = _visible_course(request, slug)
    stats = Course.objects.filter(pk=course.pk).with_stats().values(
        'students_count', 'rating_avg', 'rating_count').get()
    sections = course.sections.prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order', 'id')), 'lessons__resources')
    lesson_count = sum(len(s.lessons.all()) for s in sections)

    user = request.user
    enrollment = learning.get_active_enrollment(user, course)
    in_cart = user.is_authenticated and CartItem.objects.filter(cart__user=user, course=course).exists()
    can_review, review_block_reason = services.review_eligibility(user, course)
    my_review = course.reviews.filter(student=user).first() if user.is_authenticated else None
    reviews = course.reviews.filter(is_hidden=False).select_related('student')[:20]

    return render(request, 'courses/detail.html', {
        'course': course,
        'stats': stats,
        'sections': sections,
        'lesson_count': lesson_count,
        'enrollment': enrollment,
        'in_cart': in_cart,
        'is_owner': learning.can_manage_course(user, course),
        'can_review': can_review,
        'review_block_reason': review_block_reason,
        'my_review': my_review,
        'review_form': ReviewForm(instance=my_review),
        'reviews': reviews,
        'distribution': selectors.rating_distribution(course),
        'instructor': selectors.instructor_stats(course.instructor),
        'quiz_count': course.quizzes.filter(is_published=True).count(),
        'related': selectors.marketplace_courses().filter(category=course.category).exclude(pk=course.pk)[:4],
    })


@login_required
@require_POST
def submit_review(request, slug):
    course = _visible_course(request, slug)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please choose a rating between 1 and 5 stars.')
        return redirect(f'{course.get_absolute_url()}#reviews')
    try:
        _, created = services.save_review(request.user, course, form.cleaned_data['rating'],
                                          form.cleaned_data['comment'].strip())
    except services.ModerationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Thanks for your review!' if created else 'Your review has been updated.')
    return redirect(f'{course.get_absolute_url()}#reviews')


def instructor_profile(request, username):
    instructor = get_object_or_404(User, username=username, role=User.Role.INSTRUCTOR)
    return render(request, 'courses/instructor.html', {
        'instructor': instructor,
        'stats': selectors.instructor_stats(instructor),
    })
