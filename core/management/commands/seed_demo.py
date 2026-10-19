"""Fills the database with demo data: python manage.py seed_demo"""
import io
import random
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import InstructorApplication, User
from assessments import services as quiz_services
from assessments.models import AnswerOption, Question, Quiz
from commerce import services as commerce
from commerce.models import Order, PaymentTransaction
from core.models import Announcement, PlatformSettings, Report
from courses import services as course_services
from courses.models import Category, Course, Lesson, LessonResource, Section, Tag
from learning import services as learning
from learning.models import Enrollment

PASSWORD = 'Demo@12345'
SAMPLE_VIDEOS = [
    'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/friday.mp4',
]

CATEGORIES = [
    ('Web Development', 'Front-end, back-end and full-stack web engineering.'),
    ('Data Science', 'Analysis, statistics, machine learning and visualisation.'),
    ('Programming Languages', 'Python, JavaScript, Java and more.'),
    ('Cloud & DevOps', 'Containers, CI/CD and cloud infrastructure.'),
    ('Design', 'UI/UX, product and graphic design.'),
    ('Business', 'Management, entrepreneurship and productivity.'),
    ('Mobile Development', 'Native and cross-platform mobile apps.'),
    ('Personal Development', 'Communication, careers and learning skills.'),
]

TAGS = ['Python', 'Django', 'JavaScript', 'React', 'SQL', 'Pandas', 'Docker', 'Figma',
        'Machine Learning', 'APIs', 'Testing', 'Career']

# (title, subtitle, category, level, price, discount, instructor index, tags, status, featured)
COURSES = [
    ('Django for Beginners: Build Real Web Apps', 'From zero to a deployed, database-backed web application',
     'Web Development', 'beginner', '49.99', '14.99', 0, ['Python', 'Django', 'SQL'], 'published', True),
    ('Modern JavaScript: The Complete Guide', 'ES2023, async programming, modules and the DOM',
     'Programming Languages', 'all', '59.99', '19.99', 1, ['JavaScript'], 'published', True),
    ('Python for Data Analysis with Pandas', 'Clean, analyse and visualise real-world datasets',
     'Data Science', 'intermediate', '69.99', None, 2, ['Python', 'Pandas'], 'published', True),
    ('SQL Fundamentals in 5 Hours', 'Query relational databases with confidence',
     'Data Science', 'beginner', '29.99', None, 2, ['SQL'], 'published', False),
    ('React Essentials: Components, Hooks and State', 'Build fast, maintainable user interfaces',
     'Web Development', 'intermediate', '54.99', '24.99', 1, ['React', 'JavaScript'], 'published', False),
    ('Docker and CI/CD Pipelines', 'Containerise apps and automate delivery',
     'Cloud & DevOps', 'intermediate', '64.99', None, 0, ['Docker', 'Testing'], 'published', True),
    ('UI Design Principles with Figma', 'Layouts, typography, colour and prototyping',
     'Design', 'beginner', '39.99', None, 1, ['Figma'], 'published', False),
    ('Introduction to Machine Learning', 'Regression, classification and model evaluation',
     'Data Science', 'advanced', '89.99', '44.99', 2, ['Python', 'Machine Learning'], 'published', False),
    ('Effective Study Skills', 'Learn how to learn: memory, focus and planning',
     'Personal Development', 'all', '0', None, 0, ['Career'], 'published', False),
    ('Building REST APIs with Django REST Framework', 'Serializers, viewsets, auth and testing',
     'Web Development', 'advanced', '74.99', None, 0, ['Django', 'APIs', 'Python'], 'submitted', False),
    ('Startup Finance Basics', 'Budgets, runway and unit economics for founders',
     'Business', 'beginner', '34.99', None, 1, ['Career'], 'changes_requested', False),
    ('Flutter Mobile Apps from Scratch', 'Ship cross-platform apps with one codebase',
     'Mobile Development', 'beginner', '44.99', None, 2, [], 'draft', False),
]

SECTION_TEMPLATES = [
    ('Getting started', ['Welcome and course overview', 'Setting up your environment', 'How to get the most from this course']),
    ('Core concepts', ['Key ideas explained', 'A worked example', 'Common mistakes and how to avoid them']),
    ('Hands-on project', ['Planning the project', 'Building step by step', 'Reviewing and improving your work']),
]

REVIEW_TEXTS = [
    (5, 'Clear explanations and great pacing. The quizzes really helped the ideas stick.'),
    (5, 'Exactly what I needed. The project section ties everything together nicely.'),
    (4, 'Very good course. A few lessons could be shorter, but the content is solid.'),
    (4, 'Practical and well organised. I would love a follow-up advanced course.'),
    (3, 'Good introduction, though I expected more depth in the later sections.'),
    (5, 'The instructor explains complex topics in a really approachable way.'),
]


def make_thumbnail(title, category_index):
    from PIL import Image, ImageDraw, ImageFont

    palette = [(14, 102, 85), (29, 88, 199), (138, 83, 0), (120, 54, 160), (180, 35, 24),
               (6, 118, 71), (31, 41, 55), (161, 76, 5)]
    base = palette[category_index % len(palette)]
    img = Image.new('RGB', (1280, 720), base)
    draw = ImageDraw.Draw(img)
    light = tuple(min(255, c + 40) for c in base)
    lighter = tuple(min(255, c + 80) for c in base)
    draw.ellipse((820, -220, 1500, 460), fill=light)
    draw.ellipse((-160, 470, 300, 930), fill=light)
    draw.rounded_rectangle((900, 380, 1180, 620), radius=36, fill=lighter)
    draw.rectangle((80, 92, 200, 104), fill=(255, 255, 255))
    try:
        font = ImageFont.load_default(size=74)
        small = ImageFont.load_default(size=34)
    except TypeError:  # very old Pillow
        font = small = ImageFont.load_default()
    words, lines, line = title.split(), [], ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if draw.textlength(candidate, font=font) > 860 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    y = 150
    for text in lines[:4]:
        draw.text((80, y), text, font=font, fill=(255, 255, 255))
        y += 92
    draw.text((80, 620), 'eShikkha', font=small, fill=(255, 255, 255))
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return ContentFile(buffer.getvalue(), name=f'{slugify(title)[:60]}.png')


def make_pdf(title, lesson_title):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont('Helvetica-Bold', 18)
    c.drawString(60, height - 80, 'Lecture notes')
    c.setFont('Helvetica', 13)
    c.drawString(60, height - 105, f'{title} — {lesson_title}')
    c.setFont('Helvetica', 11)
    y = height - 150
    for i in range(1, 9):
        c.drawString(70, y, f'{i}. Key point {i}: summary of the concept discussed in this lesson.')
        y -= 22
    c.drawString(60, 60, 'eShikkha demo material')
    c.save()
    return ContentFile(buffer.getvalue(), name=f'{slugify(lesson_title)[:50]}-notes.pdf')


class Command(BaseCommand):
    help = 'Create demo users, courses, purchases, progress and reviews.'

    def add_arguments(self, parser):
        parser.add_argument('--no-media', action='store_true', help='Skip generated thumbnails and PDFs.')

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            raise CommandError('Demo data already exists. Run "python manage.py flush" first to start over.')
        self.rng = random.Random(42)
        self.media = not options['no_media']
        with transaction.atomic():
            self.seed()
        self.stdout.write(self.style.SUCCESS(
            f'\nDemo data ready. Log in with username student / instructor / admin and password {PASSWORD}'))

    def user(self, username, first, last, role, **extra):
        u = User.objects.create_user(username=username, email=f'{username}@eshikkha.local', password=PASSWORD,
                                     first_name=first, last_name=last, role=role, **extra)
        return u

    def seed(self):
        out = self.stdout
        settings = PlatformSettings.load()
        settings.save()

        admin = self.user('admin', 'Ayesha', 'Rahman', User.Role.ADMIN, is_staff=True, is_superuser=True)
        instructors = [
            self.user('instructor', 'Tanvir', 'Hasan', User.Role.INSTRUCTOR,
                      headline='Senior Software Engineer & Django contributor',
                      bio='Tanvir has built web platforms for fintech and education companies for over ten years.'
                          ' He loves turning complex topics into practical, project-based lessons.'),
            self.user('nadia', 'Nadia', 'Karim', User.Role.INSTRUCTOR,
                      headline='Front-end Lead and UI Designer',
                      bio='Nadia leads front-end teams and teaches modern JavaScript, React and interface design.'),
            self.user('farhan', 'Farhan', 'Ahmed', User.Role.INSTRUCTOR,
                      headline='Data Scientist, former university lecturer',
                      bio='Farhan has taught statistics and machine learning to thousands of students.'),
        ]
        for ins in instructors:
            InstructorApplication.objects.create(
                user=ins, headline=ins.headline, expertise='Software and data', experience='Industry experience.',
                status=InstructorApplication.Status.APPROVED, reviewed_by=admin, reviewed_at=timezone.now())

        students = [self.user('student', 'Rafi', 'Islam', User.Role.STUDENT, headline='Computer Science student')]
        names = [('Sadia', 'Chowdhury'), ('Imran', 'Hossain'), ('Mitu', 'Akter'), ('Arif', 'Khan'),
                 ('Lamia', 'Sultana'), ('Rakib', 'Uddin'), ('Tania', 'Begum'), ('Sabbir', 'Rahman'),
                 ('Nusrat', 'Jahan'), ('Fahim', 'Mahmud'), ('Priya', 'Das'), ('Zarif', 'Alam')]
        for first, last in names:
            students.append(self.user(f'{first.lower()}{last[0].lower()}', first, last, User.Role.STUDENT))
        out.write(f'  users: 1 admin, {len(instructors)} instructors, {len(students)} students')

        InstructorApplication.objects.create(
            user=students[5], headline='Mobile developer', expertise='Flutter and Kotlin',
            experience='Three years building Android apps; teaching assistant at university.',
            sample_url='https://example.com/portfolio')

        categories = []
        for i, (name, desc) in enumerate(CATEGORIES):
            categories.append(Category.objects.create(name=name, slug=slugify(name), description=desc, order=i))
        cat_by_name = {c.name: c for c in categories}
        tags = {t: Tag.objects.create(name=t, slug=slugify(t)) for t in TAGS}

        courses = []
        for idx, (title, subtitle, cat, level, price, discount, ins_i, tag_names, status, featured) in enumerate(COURSES):
            course = self.create_course(idx, title, subtitle, cat_by_name[cat], level, price, discount,
                                        instructors[ins_i], [tags[t] for t in tag_names], categories.index(cat_by_name[cat]))
            courses.append((course, status, featured))
        out.write(f'  courses: {len(courses)} with sections, lessons, materials and quizzes')

        for course, status, featured in courses:
            if status in ('published', 'submitted', 'changes_requested'):
                course_services.submit_for_review(course, course.instructor, 'Ready for review.')
            if status == 'published':
                course_services.moderate(course, admin, 'approved')
                if featured:
                    course.is_featured = True
                    course.save(update_fields=['is_featured'])
            elif status == 'changes_requested':
                course_services.moderate(course, admin, 'changes_requested',
                                         'Please add learning objectives for each section and a promo video.')

        published = [c for c, s, _ in courses if s == 'published']
        self.simulate_learning(students, published)

        Announcement.objects.create(
            title='Instructor tip', audience=Announcement.Audience.INSTRUCTORS, created_by=admin, is_active=False,
            body='Courses with a promo video and at least one free preview lesson convert better.')

        review = published[0].reviews.filter(rating__lte=4).first() or published[0].reviews.first()
        if review:
            Report.objects.create(reporter=students[3], target_type='review', review=review,
                                  reason=Report.Reason.MISLEADING, details='This review seems unrelated to the course.')
        Report.objects.create(reporter=students[2], target_type='course', course=published[1],
                              reason=Report.Reason.OTHER, details='Lesson 2 video does not load on my phone.')
        out.write('  announcements, reports and a pending instructor application created')

    def create_course(self, idx, title, subtitle, category, level, price, discount, instructor, tags, cat_index):
        topic = title.split(':')[0]
        course = Course.objects.create(
            instructor=instructor, category=category, title=title, slug=slugify(title)[:120],
            subtitle=subtitle, level=level, price=Decimal(price),
            discount_price=Decimal(discount) if discount else None,
            description=(f'{title} is a practical, project-based course.\n\n'
                         f'You will start with the fundamentals of {topic.lower()} and progressively build a complete '
                         'project. Every section ends with a short quiz so you can check your understanding, and '
                         'downloadable notes summarise each lesson.\n\nBy the end you will be able to apply these '
                         'skills confidently at work or in your own projects.'),
            learning_objectives='\n'.join([
                f'Understand the core ideas behind {topic}', 'Apply best practices used by professionals',
                'Build a complete project from scratch', 'Avoid the most common beginner mistakes',
                'Prepare for more advanced study']),
            prerequisites='A computer with internet access\nCuriosity and willingness to practise',
            target_audience=f'Beginners who want to learn {topic}\nDevelopers refreshing their skills',
            require_quizzes_for_completion=True, sequential_progression=(idx == 0),
        )
        course.tags.set(tags)
        if self.media:
            course.thumbnail.save(f'{course.slug}.png', make_thumbnail(title, cat_index), save=True)

        for s_i, (s_title, lesson_titles) in enumerate(SECTION_TEMPLATES):
            section = Section.objects.create(course=course, title=s_title, order=s_i)
            for l_i, l_title in enumerate(lesson_titles):
                is_article = l_i == 2
                lesson = Lesson.objects.create(
                    section=section, title=l_title, order=l_i,
                    lesson_type=Lesson.LessonType.ARTICLE if is_article else Lesson.LessonType.VIDEO,
                    video_url='' if is_article else SAMPLE_VIDEOS[(s_i + l_i) % 2],
                    content=(f'In this lesson, "{l_title}", we cover the essentials step by step.\n\n'
                             '• Read the overview\n• Watch or read the material\n• Download the notes\n'
                             '• Try the exercise on your own'),
                    duration_minutes=self.rng.choice([4, 6, 8, 10, 12, 15]),
                    is_preview=(s_i == 0 and l_i == 0),
                )
                if self.media and l_i == 1:
                    res = LessonResource(lesson=lesson, title=f'{l_title} – lecture notes', resource_type='pdf')
                    res.file.save('notes.pdf', make_pdf(title, l_title), save=True)
                if l_i == 0 and s_i == 1:
                    LessonResource.objects.create(lesson=lesson, title='Official documentation',
                                                  resource_type='link', url='https://docs.djangoproject.com/')
            self.create_quiz(course, section, s_i)
        return course

    def create_quiz(self, course, section, s_i):
        lesson = section.lessons.order_by('-order').first()
        final = s_i == len(SECTION_TEMPLATES) - 1
        quiz = Quiz.objects.create(
            course=course, lesson=None if final else lesson,
            title='Final assessment' if final else f'{section.title}: check your understanding',
            description='Answer the questions below. You can review your answers after submitting.',
            passing_score=70, max_attempts=3, time_limit_minutes=10 if final else None,
            result_visibility=Quiz.ResultVisibility.AFTER_FINAL if final else Quiz.ResultVisibility.FULL,
            shuffle_questions=final,
        )
        bank = [
            ('single', 'Which practice best supports long-term learning?',
             [('Spaced repetition', True), ('Cramming the night before', False), ('Skipping practice', False)]),
            ('true_false', 'Automated tests help you change code with confidence.', [('True', True), ('False', False)]),
            ('multiple', 'Which of these are good habits when building a project? (Select all that apply)',
             [('Commit small changes often', True), ('Write clear names', True), ('Never read error messages', False)]),
            ('single', 'What should you do first when you hit an unfamiliar error?',
             [('Read the error message carefully', True), ('Delete the project', False), ('Ignore it', False)]),
        ]
        for q_i, (qtype, text, options) in enumerate(bank):
            q = Question.objects.create(quiz=quiz, question_type=qtype, text=text, order=q_i, points=1,
                                        explanation='This reflects widely accepted good practice.')
            for o_i, (o_text, correct) in enumerate(options):
                AnswerOption.objects.create(question=q, text=o_text, is_correct=correct, order=o_i)

    def answer(self, attempt, correct=True):
        data = QueryDict(mutable=True)
        for q in quiz_services.ordered_questions(attempt):
            options = list(q.options.all())
            chosen = [o for o in options if o.is_correct] if correct else [o for o in options if not o.is_correct][:1]
            data.setlist(f'q{q.pk}', [str(o.pk) for o in chosen])
        return data

    def complete_course(self, enrollment, until=1.0):
        lessons = list(enrollment.course.lessons())
        cutoff = int(len(lessons) * until)
        for lesson in lessons[:cutoff]:
            try:
                learning.mark_lesson_complete(enrollment, lesson)
            except learning.EnrollmentError:
                pass
            learning.touch_lesson(enrollment, lesson)
        if until >= 1.0:
            for quiz in enrollment.course.quizzes.filter(is_published=True):
                attempt = quiz_services.start_attempt(quiz, enrollment.student)
                quiz_services.submit_attempt(attempt.pk, enrollment.student, self.answer(attempt))

    def simulate_learning(self, students, published):
        rng = self.rng
        now = timezone.now()
        main = students[0]
        paid = [c for c in published if not c.is_free]
        free = [c for c in published if c.is_free]

        # main demo account: one finished course, a few in progress
        order = commerce.create_order(main, [paid[0].pk, paid[2].pk])
        commerce.process_payment(order.order_number, main, PaymentTransaction.Outcome.SUCCESS)
        order = commerce.create_order(main, [paid[1].pk])
        commerce.process_payment(order.order_number, main, PaymentTransaction.Outcome.DECLINE)
        commerce.process_payment(order.order_number, main, PaymentTransaction.Outcome.SUCCESS)
        for c in free:
            learning.enroll(main, c, Enrollment.Source.FREE)
        e = Enrollment.objects.get(student=main, course=paid[0])
        self.complete_course(e)
        course_services.save_review(main, paid[0], 5, 'Fantastic introduction — I built my first app in a weekend!')
        self.complete_course(Enrollment.objects.get(student=main, course=paid[2]), until=0.45)
        self.complete_course(Enrollment.objects.get(student=main, course=paid[1]), until=0.2)
        commerce.add_to_cart(main, paid[4])
        cancelled = commerce.create_order(main, [paid[3].pk])
        commerce.process_payment(cancelled.order_number, main, PaymentTransaction.Outcome.CANCEL)

        for student in students[1:]:
            picks = rng.sample(paid, k=rng.randint(1, 4))
            order = commerce.create_order(student, [c.pk for c in picks])
            commerce.process_payment(order.order_number, student, PaymentTransaction.Outcome.SUCCESS)
            if free and rng.random() < 0.5:
                learning.enroll(student, free[0], Enrollment.Source.FREE)
            for course in picks:
                enrollment = Enrollment.objects.get(student=student, course=course)
                level = rng.choice([0.15, 0.4, 0.7, 1.0])
                self.complete_course(enrollment, until=level)
                enrollment.refresh_from_db()
                if enrollment.progress_percent >= 10 and rng.random() < 0.75:
                    rating, text = rng.choice(REVIEW_TEXTS)
                    course_services.save_review(student, course, rating, text)

        # backdate orders so the charts have something to show
        for order in Order.objects.all():
            shift = timedelta(days=rng.randint(1, 170), hours=rng.randint(0, 23))
            Order.objects.filter(pk=order.pk).update(created_at=order.created_at - shift,
                                                     paid_at=order.paid_at - shift if order.paid_at else None)
            order.transactions.update(created_at=order.created_at - shift,
                                      processed_at=order.created_at - shift + timedelta(minutes=1))
            for item in order.items.all():
                if hasattr(item, 'earning'):
                    type(item.earning).objects.filter(pk=item.earning.pk).update(created_at=order.created_at - shift)
            Enrollment.objects.filter(order=order).update(enrolled_at=order.created_at - shift)
        for enrollment in Enrollment.objects.filter(last_accessed_at__isnull=False):
            Enrollment.objects.filter(pk=enrollment.pk).update(
                last_accessed_at=now - timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 23)))
        Enrollment.objects.filter(student=main).update(last_accessed_at=now - timedelta(hours=2))
        self.stdout.write(f'  enrolments: {Enrollment.objects.count()}, orders: {Order.objects.count()}, '
                          f'transactions: {PaymentTransaction.objects.count()}')
