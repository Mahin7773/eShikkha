from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Quiz(models.Model):
    class ResultVisibility(models.TextChoices):
        FULL = 'full', 'Score and correct answers immediately'
        AFTER_FINAL = 'after_final', 'Score now; correct answers after passing or using all attempts'
        SCORE_ONLY = 'score', 'Score only (never reveal correct answers)'

    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='quizzes')
    lesson = models.ForeignKey('courses.Lesson', null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='quizzes',
                               help_text='Attach to a lesson, or leave empty for a course-level (final) quiz.')
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    passing_score = models.PositiveSmallIntegerField(
        default=70, validators=[MinValueValidator(1), MaxValueValidator(100)], help_text='Percent required to pass.')
    time_limit_minutes = models.PositiveSmallIntegerField(null=True, blank=True,
                                                          help_text='Leave empty for no time limit.')
    max_attempts = models.PositiveSmallIntegerField(default=3, help_text='0 = unlimited attempts.')
    shuffle_questions = models.BooleanField(default=False)
    result_visibility = models.CharField(max_length=12, choices=ResultVisibility.choices,
                                         default=ResultVisibility.AFTER_FINAL)
    show_explanations = models.BooleanField(default=True,
                                            help_text='Show explanations when correct answers are revealed.')
    is_required = models.BooleanField(default=True, help_text='Must be passed to complete the course.')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name_plural = 'quizzes'

    def __str__(self):
        return self.title

    @property
    def unlimited_attempts(self):
        return self.max_attempts == 0

    def validation_errors(self):
        errors = []
        questions = list(self.questions.prefetch_related('options'))
        if not questions:
            errors.append(f'Quiz "{self.title}" has no questions.')
        for q in questions:
            errors.extend(f'Quiz "{self.title}": {e}' for e in q.validation_errors())
        return errors


class Question(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE = 'single', 'Multiple choice (one answer)'
        MULTIPLE = 'multiple', 'Multiple choice (several answers)'
        TRUE_FALSE = 'true_false', 'True / False'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=12, choices=QuestionType.choices, default=QuestionType.SINGLE)
    text = models.TextField()
    explanation = models.TextField(blank=True, help_text='Shown after the answer is revealed.')
    points = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:80]

    @property
    def is_multi_select(self):
        return self.question_type == self.QuestionType.MULTIPLE

    def correct_option_ids(self):
        return {o.id for o in self.options.all() if o.is_correct}

    def validation_errors(self):
        options = list(self.options.all())
        correct = sum(o.is_correct for o in options)
        label = f'question "{self.text[:40]}"'
        if len(options) < 2:
            return [f'{label} needs at least two options.']
        if self.question_type == self.QuestionType.TRUE_FALSE and len(options) != 2:
            return [f'{label} must have exactly two options (True and False).']
        if self.question_type in (self.QuestionType.SINGLE, self.QuestionType.TRUE_FALSE) and correct != 1:
            return [f'{label} must have exactly one correct option.']
        if self.question_type == self.QuestionType.MULTIPLE and correct < 1:
            return [f'{label} must have at least one correct option.']
        return []


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In progress'
        SUBMITTED = 'submitted', 'Submitted'
        EXPIRED = 'expired', 'Time expired'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    attempt_number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)
    question_order = models.JSONField(default=list, help_text='Question ids in the order presented.')
    started_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    points_possible = models.PositiveIntegerField(default=0)
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'student', 'attempt_number'], name='unique_attempt_number'),
            models.UniqueConstraint(fields=['quiz', 'student'], condition=Q(status='in_progress'),
                                    name='one_open_attempt_per_quiz'),
        ]
        indexes = [models.Index(fields=['quiz', 'student'])]

    def __str__(self):
        return f'{self.student} – {self.quiz} #{self.attempt_number}'

    @property
    def is_open(self):
        return self.status == self.Status.IN_PROGRESS


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attempt_answers')
    selected_options = models.ManyToManyField(AnswerOption, blank=True, related_name='selections')
    is_correct = models.BooleanField(default=False)
    points_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'question'], name='one_answer_per_question_per_attempt'),
        ]
