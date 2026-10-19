from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils.text import slugify

from assessments.models import AttemptAnswer, QuizAttempt
from commerce.models import InstructorEarning
from courses.models import Course
from learning.models import Enrollment

RESERVED_SLUGS = {'certificates', 'instructors', 'new', 'edit'}


def owned_course(user, pk):
    return get_object_or_404(Course, pk=pk, instructor=user)


class CourseLocked(Exception):
    """Handled by studio.middleware (shows a message and redirects)."""

    def __init__(self, course, message):
        super().__init__(message)
        self.course = course


def ensure_editable(course):
    if course.status == Course.Status.SUBMITTED:
        raise CourseLocked(course, 'This course is under review and locked for editing until a decision is made.')
    if course.status == Course.Status.ARCHIVED:
        raise CourseLocked(course, 'Archived courses must be restored to draft before editing.')


def unique_slug(title, exclude_pk=None):
    base = slugify(title)[:120] or 'course'
    if base in RESERVED_SLUGS:
        base = f'{base}-course'
    slug, n = base, 2
    qs = Course.objects.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


def move(obj, siblings, direction):
    items = list(siblings)
    for i, item in enumerate(items):
        if item.order != i:
            item.order = i
            item.save(update_fields=['order'])
    idx = next(i for i, item in enumerate(items) if item.pk == obj.pk)
    target = idx - 1 if direction == 'up' else idx + 1
    if 0 <= target < len(items):
        a, b = items[idx], items[target]
        a.order, b.order = b.order, a.order
        a.save(update_fields=['order'])
        b.save(update_fields=['order'])


def next_order(qs):
    return (qs.aggregate(m=Max('order'))['m'] or 0) + 1


def earnings_summary(instructor):
    recorded = InstructorEarning.objects.filter(instructor=instructor, status=InstructorEarning.Status.RECORDED)
    totals = recorded.aggregate(gross=Sum('gross_amount'), fee=Sum('platform_fee'), net=Sum('net_amount'),
                                sales=Count('pk'))
    reversed_total = (InstructorEarning.objects.filter(instructor=instructor, status=InstructorEarning.Status.REVERSED)
                      .aggregate(n=Sum('net_amount'))['n'] or Decimal(0))
    monthly = (recorded.annotate(month=TruncMonth('created_at')).values('month')
               .annotate(sales=Count('pk'), gross=Sum('gross_amount'), net=Sum('net_amount')).order_by('-month')[:12])
    by_course = (recorded.values('course__title', 'course_id')
                 .annotate(sales=Count('pk'), gross=Sum('gross_amount'), fee=Sum('platform_fee'),
                           net=Sum('net_amount')).order_by('-net'))
    monthly = list(monthly)
    peak = max((m['net'] for m in monthly), default=0) or 1
    for m in monthly:
        m['bar'] = int(m['net'] * 100 / peak)
    return {
        'gross': totals['gross'] or Decimal(0), 'fee': totals['fee'] or Decimal(0),
        'net': totals['net'] or Decimal(0), 'sales': totals['sales'], 'reversed': reversed_total,
        'monthly': monthly, 'by_course': by_course,
    }


def course_quiz_stats(course):
    stats = []
    for quiz in course.quizzes.prefetch_related('questions'):
        attempts = QuizAttempt.objects.filter(quiz=quiz).exclude(status=QuizAttempt.Status.IN_PROGRESS)
        agg = attempts.aggregate(n=Count('pk'), avg=Avg('score_percent'), passed=Count('pk', filter=Q(passed=True)),
                                 students=Count('student', distinct=True))
        questions = []
        answer_stats = {row['question']: row for row in AttemptAnswer.objects.filter(attempt__in=attempts)
                        .values('question').annotate(n=Count('pk'), correct=Count('pk', filter=Q(is_correct=True)))}
        for q in quiz.questions.all():
            row = answer_stats.get(q.id, {'n': 0, 'correct': 0})
            questions.append({'question': q, 'answered': row['n'],
                              'correct_rate': round(row['correct'] * 100 / row['n']) if row['n'] else None})
        stats.append({
            'quiz': quiz, 'attempts': agg['n'], 'students': agg['students'],
            'avg': agg['avg'], 'pass_rate': round(agg['passed'] * 100 / agg['n']) if agg['n'] else None,
            'questions': questions,
        })
    return stats


def course_overview_stats(course):
    enrollments = Enrollment.objects.filter(course=course, status=Enrollment.Status.ACTIVE)
    agg = enrollments.aggregate(n=Count('pk'), done=Count('pk', filter=Q(completed_at__isnull=False)),
                                avg=Avg('progress_percent'))
    reviews = course.reviews.filter(is_hidden=False).aggregate(n=Count('pk'), avg=Avg('rating'))
    earn = (InstructorEarning.objects.filter(course=course, status=InstructorEarning.Status.RECORDED)
            .aggregate(net=Sum('net_amount'), sales=Count('pk')))
    return {
        'students': agg['n'], 'completed': agg['done'],
        'completion_rate': round(agg['done'] * 100 / agg['n']) if agg['n'] else 0,
        'avg_progress': round(agg['avg'] or 0),
        'reviews': reviews['n'], 'rating': reviews['avg'] or 0,
        'net': earn['net'] or Decimal(0), 'sales': earn['sales'],
    }


def student_quiz_scores(course):
    best = defaultdict(dict)
    rows = (QuizAttempt.objects.filter(quiz__course=course).exclude(status=QuizAttempt.Status.IN_PROGRESS)
            .values('student_id', 'quiz_id').annotate(best=Max('score_percent'), n=Count('pk')))
    for row in rows:
        best[row['student_id']][row['quiz_id']] = row
    return best
