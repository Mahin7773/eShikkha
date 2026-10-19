from django.contrib import admin

from .models import AnswerOption, AttemptAnswer, Question, Quiz, QuizAttempt


class OptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'question_type', 'points')
    inlines = [OptionInline]


admin.site.register([Quiz, QuizAttempt, AttemptAnswer])
