from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from assessments.models import Question, Quiz
from core.models import PlatformSettings
from core.permissions import instructor_required
from courses import services as course_services
from courses.models import Course, Lesson, LessonResource, Section
from learning.models import Enrollment

from . import services
from .forms import (CourseForm, LessonForm, ModerationNoteForm, OptionFormSet, QuestionForm, QuizForm,
                    ResourceForm, SectionForm)


def _course(request, pk, editable=False):
    course = services.owned_course(request.user, pk)
    if editable:
        services.ensure_editable(course)
    return course


def _after_edit(request, course):
    if course_services.after_instructor_edit(course, request.user, request):
        messages.info(request, 'Platform policy requires re-review of edited published courses. '
                               'It has been resubmitted; enrolled students keep access.')


@instructor_required
def dashboard(request):
    courses = (Course.objects.filter(instructor=request.user).with_stats()
               .select_related('category').order_by('-updated_at'))
    recent = (Enrollment.objects.filter(course__instructor=request.user)
              .select_related('student', 'course')[:8])
    status_counts = dict(courses.values_list('status').annotate(n=Count('pk')).order_by())
    return render(request, 'studio/dashboard.html', {
        'courses': courses,
        'recent_enrollments': recent,
        'earnings': services.earnings_summary(request.user),
        'totals': {
            'courses': len(courses),
            'published': status_counts.get(Course.Status.PUBLISHED, 0),
            'in_review': status_counts.get(Course.Status.SUBMITTED, 0),
            'students': sum(c.students_count for c in courses),
            'reviews': sum(c.rating_count for c in courses),
        },
    })


@instructor_required
def course_create(request):
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.slug = services.unique_slug(course.title)
            course.save()
            form.save_m2m()
            messages.success(request, 'Course created as a draft. Now build your curriculum.')
            return redirect('studio:curriculum', course.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'studio/course_form.html', {'form': form, 'creating': True,
                                                       'platform_settings': PlatformSettings.load()})


@instructor_required
def course_overview(request, pk):
    course = _course(request, pk)
    return render(request, 'studio/course_overview.html', {
        'course': course, 'tab': 'overview',
        'stats': services.course_overview_stats(course),
        'problems': course_services.readiness_problems(course) if course.can_be_submitted else [],
        'timeline': course.moderation_decisions.select_related('actor')[:20],
        'note_form': ModerationNoteForm(),
        'lesson_count': course.lessons().count(),
        'quiz_count': course.quizzes.count(),
    })


@instructor_required
def course_edit(request, pk):
    course = _course(request, pk, editable=True)
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    if request.method == 'POST':
        if form.is_valid():
            old_title = Course.objects.get(pk=course.pk).title
            course = form.save(commit=False)
            if course.title != old_title and course.status != Course.Status.PUBLISHED:
                course.slug = services.unique_slug(course.title, exclude_pk=course.pk)
            course.save()
            form.save_m2m()
            messages.success(request, 'Course details saved.')
            _after_edit(request, course)
            return redirect('studio:course_edit', course.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'studio/course_form.html', {'form': form, 'course': course, 'tab': 'details',
                                                       'platform_settings': PlatformSettings.load()})


@instructor_required
@require_POST
def course_submit(request, pk):
    course = _course(request, pk)
    form = ModerationNoteForm(request.POST)
    note = form.cleaned_data['note'] if form.is_valid() else ''
    try:
        course_services.submit_for_review(course, request.user, note, request)
    except course_services.ModerationError as exc:
        messages.error(request, str(exc))
    else:
        course.refresh_from_db()
        if course.is_published:
            messages.success(request, 'Your course is live in the marketplace.')
        else:
            messages.success(request, 'Submitted for review. You will be notified of the decision.')
    return redirect('studio:course', course.pk)


@instructor_required
@require_POST
def course_archive(request, pk):
    course = _course(request, pk)
    try:
        course_services.instructor_archive(course, request.user, request)
        messages.success(request, 'Course archived. It is hidden from the marketplace; enrolled students keep access.')
    except course_services.ModerationError as exc:
        messages.error(request, str(exc))
    return redirect('studio:course', course.pk)


@instructor_required
@require_POST
def course_restore(request, pk):
    course = _course(request, pk)
    try:
        course_services.instructor_restore(course, request.user, request)
        messages.success(request, 'Course restored to draft.')
    except course_services.ModerationError as exc:
        messages.error(request, str(exc))
    return redirect('studio:course', course.pk)


@instructor_required
@require_POST
def course_delete(request, pk):
    course = _course(request, pk)
    if course.status != Course.Status.DRAFT or course.enrollments.exists() or course.order_items.exists():
        messages.error(request, 'Only unpublished drafts without students or orders can be deleted. Archive it instead.')
        return redirect('studio:course', course.pk)
    title = course.title
    course.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect('studio:dashboard')


@instructor_required
def curriculum(request, pk):
    course = _course(request, pk)
    sections = course.sections.prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order', 'id')
                 .annotate(resource_count=Count('resources')).prefetch_related('quizzes')))
    return render(request, 'studio/curriculum.html', {
        'course': course, 'tab': 'curriculum', 'sections': sections,
        'editable': course.status not in (Course.Status.SUBMITTED, Course.Status.ARCHIVED),
        'section_form': SectionForm(),
        'final_quizzes': course.quizzes.filter(lesson__isnull=True),
    })


@instructor_required
@require_POST
def section_create(request, pk):
    course = _course(request, pk, editable=True)
    form = SectionForm(request.POST)
    if form.is_valid():
        section = form.save(commit=False)
        section.course = course
        section.order = services.next_order(course.sections.all())
        section.save()
        messages.success(request, f'Section "{section.title}" added.')
    else:
        messages.error(request, 'Section title is required.')
    return redirect('studio:curriculum', course.pk)


@instructor_required
def section_edit(request, pk, section_id):
    course = _course(request, pk, editable=True)
    section = get_object_or_404(Section, pk=section_id, course=course)
    form = SectionForm(request.POST or None, instance=section)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Section renamed.')
        return redirect('studio:curriculum', course.pk)
    return render(request, 'studio/simple_form.html', {
        'course': course, 'form': form, 'title': 'Rename section', 'tab': 'curriculum',
        'cancel_url': f'/teach/courses/{course.pk}/curriculum/'})


@instructor_required
@require_POST
def section_delete(request, pk, section_id):
    course = _course(request, pk, editable=True)
    section = get_object_or_404(Section, pk=section_id, course=course)
    section.delete()
    messages.success(request, 'Section deleted.')
    return redirect('studio:curriculum', course.pk)


@instructor_required
@require_POST
def section_move(request, pk, section_id, direction):
    course = _course(request, pk, editable=True)
    section = get_object_or_404(Section, pk=section_id, course=course)
    services.move(section, course.sections.all(), direction)
    return redirect('studio:curriculum', course.pk)


@instructor_required
def lesson_create(request, pk, section_id):
    course = _course(request, pk, editable=True)
    section = get_object_or_404(Section, pk=section_id, course=course)
    form = LessonForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.section = section
            lesson.order = services.next_order(section.lessons.all())
            lesson.save()
            messages.success(request, 'Lesson added. You can attach lecture materials below.')
            _after_edit(request, course)
            return redirect('studio:lesson_edit', course.pk, lesson.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'studio/lesson_form.html', {'course': course, 'section': section, 'form': form,
                                                       'tab': 'curriculum'})


@instructor_required
def lesson_edit(request, pk, lesson_id):
    course = _course(request, pk, editable=True)
    lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
    form = LessonForm(request.POST or None, request.FILES or None, instance=lesson)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Lesson saved.')
            _after_edit(request, course)
            return redirect('studio:lesson_edit', course.pk, lesson.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'studio/lesson_form.html', {
        'course': course, 'section': lesson.section, 'lesson': lesson, 'form': form, 'tab': 'curriculum',
        'resource_form': ResourceForm(), 'resources': lesson.resources.all()})


@instructor_required
@require_POST
def lesson_delete(request, pk, lesson_id):
    course = _course(request, pk, editable=True)
    lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
    lesson.delete()
    messages.success(request, 'Lesson deleted.')
    return redirect('studio:curriculum', course.pk)


@instructor_required
@require_POST
def lesson_move(request, pk, lesson_id, direction):
    course = _course(request, pk, editable=True)
    lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
    services.move(lesson, lesson.section.lessons.all(), direction)
    return redirect('studio:curriculum', course.pk)


@instructor_required
@require_POST
def resource_create(request, pk, lesson_id):
    course = _course(request, pk, editable=True)
    lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
    form = ResourceForm(request.POST, request.FILES)
    if form.is_valid():
        resource = form.save(commit=False)
        resource.lesson = lesson
        resource.save()
        messages.success(request, f'Material "{resource.title}" added.')
    else:
        errors = '; '.join(e for errs in form.errors.values() for e in errs)
        messages.error(request, f'Could not add material: {errors}')
    return redirect('studio:lesson_edit', course.pk, lesson.pk)


@instructor_required
@require_POST
def resource_delete(request, pk, resource_id):
    course = _course(request, pk, editable=True)
    resource = get_object_or_404(LessonResource, pk=resource_id, lesson__section__course=course)
    lesson_id = resource.lesson_id
    resource.delete()
    messages.success(request, 'Material removed.')
    return redirect('studio:lesson_edit', course.pk, lesson_id)


@instructor_required
def quiz_list(request, pk):
    course = _course(request, pk)
    quizzes = course.quizzes.select_related('lesson').annotate(
        question_count=Count('questions', distinct=True), attempt_count=Count('attempts', distinct=True))
    return render(request, 'studio/quiz_list.html', {'course': course, 'quizzes': quizzes, 'tab': 'quizzes',
                                                     'editable': course.status not in (Course.Status.SUBMITTED, Course.Status.ARCHIVED)})


@instructor_required
def quiz_form(request, pk, quiz_id=None):
    course = _course(request, pk, editable=True)
    quiz = get_object_or_404(Quiz, pk=quiz_id, course=course) if quiz_id else None
    initial = {'lesson': request.GET.get('lesson')} if not quiz else None
    form = QuizForm(request.POST or None, instance=quiz, course=course, initial=initial)
    if request.method == 'POST':
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.course = course
            quiz.save()
            messages.success(request, 'Quiz saved. Add or edit its questions below.')
            return redirect('studio:quiz_questions', course.pk, quiz.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'studio/quiz_form.html', {'course': course, 'quiz': quiz, 'form': form, 'tab': 'quizzes'})


@instructor_required
def quiz_questions(request, pk, quiz_id):
    course = _course(request, pk)
    quiz = get_object_or_404(Quiz, pk=quiz_id, course=course)
    return render(request, 'studio/quiz_questions.html', {
        'course': course, 'quiz': quiz, 'tab': 'quizzes',
        'questions': quiz.questions.prefetch_related('options'),
        'problems': quiz.validation_errors(),
        'editable': course.status not in (Course.Status.SUBMITTED, Course.Status.ARCHIVED),
    })


@instructor_required
@require_POST
def quiz_delete(request, pk, quiz_id):
    course = _course(request, pk, editable=True)
    quiz = get_object_or_404(Quiz, pk=quiz_id, course=course)
    if quiz.attempts.exists():
        quiz.is_published = False
        quiz.save(update_fields=['is_published'])
        messages.info(request, 'This quiz has student attempts, so it was unpublished instead of deleted.')
    else:
        quiz.delete()
        messages.success(request, 'Quiz deleted.')
    return redirect('studio:quizzes', course.pk)


@instructor_required
def question_form(request, pk, quiz_id, question_id=None):
    course = _course(request, pk, editable=True)
    quiz = get_object_or_404(Quiz, pk=quiz_id, course=course)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz) if question_id else Question(quiz=quiz)
    qtype_param = request.GET.get('type')
    form = QuestionForm(request.POST or None, instance=question,
                        initial={'question_type': qtype_param} if qtype_param and not question_id else None)
    if question_id:
        qtype = request.POST.get('question_type') or question.question_type
    else:
        qtype = request.POST.get('question_type') or qtype_param or Question.QuestionType.SINGLE
    formset = OptionFormSet(request.POST or None, instance=question, question_type=qtype, prefix='options')
    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                question = form.save(commit=False)
                question.quiz = quiz
                if not question.pk:
                    question.order = services.next_order(quiz.questions.all())
                question.save()
                formset.instance = question
                options = formset.save(commit=False)
                for obj in formset.deleted_objects:
                    obj.delete()
                for i, option in enumerate(options):
                    if option.text:
                        option.order = i
                        option.save()
            messages.success(request, 'Question saved.')
            if 'add_another' in request.POST:
                return redirect(f'/teach/courses/{course.pk}/quizzes/{quiz.pk}/questions/new/?type={question.question_type}')
            return redirect('studio:quiz_questions', course.pk, quiz.pk)
        messages.error(request, 'Please correct the problems below.')
    return render(request, 'studio/question_form.html', {
        'course': course, 'quiz': quiz, 'question': question if question_id else None,
        'form': form, 'formset': formset, 'tab': 'quizzes',
        # prefilled in the template; formset initial data would be skipped as "unchanged"
        'prefill_tf': not question_id and not request.POST and qtype == Question.QuestionType.TRUE_FALSE})


@instructor_required
@require_POST
def question_delete(request, pk, quiz_id, question_id):
    course = _course(request, pk, editable=True)
    question = get_object_or_404(Question, pk=question_id, quiz__course=course, quiz_id=quiz_id)
    if question.attempt_answers.exists():
        messages.error(request, 'Students have answered this question; it cannot be deleted. Edit it instead.')
    else:
        question.delete()
        messages.success(request, 'Question deleted.')
    return redirect('studio:quiz_questions', course.pk, quiz_id)


@instructor_required
def course_students(request, pk):
    course = _course(request, pk)
    enrollments = (course.enrollments.select_related('student', 'last_lesson')
                   .annotate(lessons_done=Count('completions')).order_by('-enrolled_at'))
    q = request.GET.get('q', '').strip()
    if q:
        enrollments = enrollments.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q)
                                         | Q(student__username__icontains=q))
    status = request.GET.get('status')
    if status == 'completed':
        enrollments = enrollments.filter(completed_at__isnull=False)
    elif status == 'in_progress':
        enrollments = enrollments.filter(completed_at__isnull=True, status=Enrollment.Status.ACTIVE)
    page = Paginator(enrollments, 25).get_page(request.GET.get('page'))
    quizzes = list(course.quizzes.filter(is_published=True))
    scores = services.student_quiz_scores(course)
    rows = [{'enrollment': e, 'scores': [scores.get(e.student_id, {}).get(qz.id) for qz in quizzes]}
            for e in page]
    return render(request, 'studio/students.html', {
        'course': course, 'tab': 'students', 'page_obj': page, 'rows': rows, 'quizzes': quizzes,
        'total_lessons': course.lessons().count(), 'q': q, 'status': status,
    })


@instructor_required
def course_analytics(request, pk):
    course = _course(request, pk)
    return render(request, 'studio/analytics.html', {
        'course': course, 'tab': 'analytics',
        'stats': services.course_overview_stats(course),
        'quiz_stats': services.course_quiz_stats(course),
    })


@instructor_required
def course_reviews(request, pk):
    course = _course(request, pk)
    from courses.selectors import rating_distribution
    return render(request, 'studio/reviews.html', {
        'course': course, 'tab': 'reviews',
        'reviews': course.reviews.filter(is_hidden=False).select_related('student'),
        'distribution': rating_distribution(course),
        'stats': services.course_overview_stats(course),
    })


@instructor_required
def earnings(request):
    return render(request, 'studio/earnings.html', {
        'earnings': services.earnings_summary(request.user),
        'fee_percent': PlatformSettings.load().platform_fee_percent,
        'recent': request.user.earnings.select_related('course', 'order_item__order')[:25],
    })
