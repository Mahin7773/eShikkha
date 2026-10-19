"""Helpers for creating test data."""
from decimal import Decimal
from itertools import count

from accounts.models import User
from assessments.models import AnswerOption, Question, Quiz
from courses.models import Category, Course, Lesson, Section

_seq = count(1)


def make_user(role=User.Role.STUDENT, **extra):
    n = next(_seq)
    return User.objects.create_user(username=f'user{n}', email=f'user{n}@test.local', password='pw-Test-123',
                                    role=role, first_name='Test', last_name=f'User{n}', **extra)


def make_course(instructor=None, price='20.00', status=Course.Status.PUBLISHED, lessons=3, **extra):
    n = next(_seq)
    instructor = instructor or make_user(User.Role.INSTRUCTOR)
    category, _ = Category.objects.get_or_create(name='Testing', slug='testing')
    course = Course.objects.create(
        instructor=instructor, category=category, title=f'Course {n}', slug=f'course-{n}',
        description='Description', learning_objectives='Learn things', price=Decimal(price), status=status, **extra)
    section = Section.objects.create(course=course, title='Section 1')
    for i in range(lessons):
        Lesson.objects.create(section=section, title=f'Lesson {i + 1}', order=i, video_url='https://example.com/v.mp4',
                              is_preview=(i == 0))
    return course


def make_quiz(course, lesson=None, max_attempts=2, **extra):
    quiz = Quiz.objects.create(course=course, lesson=lesson, title='Quiz', passing_score=50,
                               max_attempts=max_attempts, **extra)
    q = Question.objects.create(quiz=quiz, question_type=Question.QuestionType.SINGLE, text='2 + 2 = ?')
    right = AnswerOption.objects.create(question=q, text='4', is_correct=True)
    wrong = AnswerOption.objects.create(question=q, text='5', is_correct=False)
    return quiz, q, right, wrong
