from django.db.models import Avg, Case, Count, DecimalField, F, Q, When
from django.utils import timezone

from accounts.models import User

from .models import Course, Review

SORT_OPTIONS = {
    'popular': ('Most popular', ['-students_count', '-rating_avg']),
    'rating': ('Highest rated', ['-rating_avg', '-rating_count']),
    'newest': ('Newest', ['-published_at']),
    'price_low': ('Price: low to high', ['effective_price', '-students_count']),
    'price_high': ('Price: high to low', ['-effective_price', '-students_count']),
}

PRICE_FILTERS = {
    'free': ('Free', Q(effective_price=0)),
    'paid': ('Paid', Q(effective_price__gt=0)),
    'under20': ('Under $20', Q(effective_price__gt=0, effective_price__lt=20)),
    '20to50': ('$20 – $50', Q(effective_price__gte=20, effective_price__lte=50)),
    'over50': ('Over $50', Q(effective_price__gt=50)),
}

RATING_FILTERS = {'4.5': 4.5, '4': 4.0, '3.5': 3.5, '3': 3.0}


def marketplace_courses():
    now = timezone.now()
    active_discount = Q(discount_price__isnull=False, discount_price__lt=F('price')) & (
        Q(discount_ends_at__isnull=True) | Q(discount_ends_at__gt=now))
    return (Course.objects.published().with_stats()
            .annotate(effective_price=Case(When(active_discount, then=F('discount_price')),
                                           default=F('price'), output_field=DecimalField()))
            .select_related('instructor', 'category'))


def search_courses(params):
    qs = marketplace_courses()
    applied = {}

    if q := params.get('q', '').strip():
        terms = q.split()
        for term in terms:
            qs = qs.filter(
                Q(title__icontains=term) | Q(subtitle__icontains=term) | Q(description__icontains=term)
                | Q(instructor__first_name__icontains=term) | Q(instructor__last_name__icontains=term)
                | Q(instructor__username__icontains=term) | Q(tags__name__icontains=term)
                | Q(category__name__icontains=term))
        qs = qs.distinct()
        applied['q'] = q

    categories = [c for c in params.getlist('category') if c]
    if categories:
        qs = qs.filter(category__slug__in=categories)
        applied['category'] = categories

    levels = [lv for lv in params.getlist('level') if lv in Course.Level.values]
    if levels:
        qs = qs.filter(level__in=levels)
        applied['level'] = levels

    if (price := params.get('price')) in PRICE_FILTERS:
        qs = qs.filter(PRICE_FILTERS[price][1])
        applied['price'] = price

    if (rating := params.get('rating')) in RATING_FILTERS:
        qs = qs.filter(rating_avg__gte=RATING_FILTERS[rating])
        applied['rating'] = rating

    if tag := params.get('tag'):
        qs = qs.filter(tags__slug=tag).distinct()
        applied['tag'] = tag

    sort = params.get('sort') if params.get('sort') in SORT_OPTIONS else 'popular'
    qs = qs.order_by(*SORT_OPTIONS[sort][1], 'pk')
    return qs, applied, sort


def rating_distribution(course):
    counts = dict(Review.objects.filter(course=course, is_hidden=False)
                  .values_list('rating').annotate(n=Count('pk')))
    total = sum(counts.values()) or 1
    return [{'stars': s, 'count': counts.get(s, 0), 'percent': round(counts.get(s, 0) * 100 / total)}
            for s in range(5, 0, -1)]


def instructor_stats(instructor):
    courses = Course.objects.published().filter(instructor=instructor).with_stats()
    reviews = Review.objects.filter(course__instructor=instructor, is_hidden=False)
    return {
        'courses': courses,
        'course_count': courses.count(),
        'students': sum(c.students_count for c in courses),
        'reviews': reviews.count(),
        'rating': reviews.aggregate(a=Avg('rating'))['a'] or 0,
    }


def top_instructors(limit=4):
    instructors = (User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True,
                                       courses_taught__status=Course.Status.PUBLISHED)
                   .annotate(rating=Avg('courses_taught__reviews__rating',
                                        filter=Q(courses_taught__reviews__is_hidden=False)),
                             students=Count('courses_taught__enrollments', distinct=True,
                                            filter=Q(courses_taught__enrollments__status='active')),
                             course_count=Count('courses_taught', distinct=True,
                                                filter=Q(courses_taught__status=Course.Status.PUBLISHED)))
                   .order_by(F('rating').desc(nulls_last=True), '-students')
                   .distinct())
    return instructors[:limit]
