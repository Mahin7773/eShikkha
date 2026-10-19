from django import forms
from django.forms import inlineformset_factory

from assessments.models import AnswerOption, Question, Quiz
from core.models import PlatformSettings
from courses.models import Category, Course, Lesson, LessonResource, Section, Tag


class CourseForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,
                                          widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Course
        fields = (
            'title', 'subtitle', 'category', 'level', 'language', 'tags',
            'description', 'learning_objectives', 'prerequisites', 'target_audience',
            'thumbnail', 'promo_video', 'promo_video_url',
            'price', 'discount_price', 'discount_ends_at',
            'sequential_progression', 'require_quizzes_for_completion', 'certificate_enabled',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'learning_objectives': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Build a REST API with Django\nWrite automated tests'}),
            'prerequisites': forms.Textarea(attrs={'rows': 3}),
            'target_audience': forms.Textarea(attrs={'rows': 3}),
            'discount_ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'discount_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
        labels = {'price': 'Price (USD)', 'discount_price': 'Discounted price (optional)',
                  'promo_video_url': 'Promo video URL'}
        help_texts = {'price': 'Set 0 for a free course.',
                      'discount_ends_at': 'Leave empty for an open-ended discount.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = PlatformSettings.load()
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['discount_ends_at'].input_formats = ['%Y-%m-%dT%H:%M']
        if not self.settings.allow_discounts:
            for name in ('discount_price', 'discount_ends_at'):
                self.fields[name].disabled = True
                self.fields[name].help_text = 'Discounts are currently disabled by the platform.'

    def clean_price(self):
        price = self.cleaned_data['price']
        if price > self.settings.max_course_price:
            raise forms.ValidationError(f'The maximum course price is ${self.settings.max_course_price}.')
        return price

    def clean(self):
        data = super().clean()
        price, discount = data.get('price'), data.get('discount_price')
        if not self.settings.allow_discounts:
            data['discount_price'] = None
            data['discount_ends_at'] = None
        elif discount is not None and price is not None and discount >= price:
            self.add_error('discount_price', 'The discounted price must be lower than the regular price.')
        return data


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ('title',)


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ('title', 'lesson_type', 'video_file', 'video_url', 'duration_minutes', 'content',
                  'is_preview', 'is_required', 'completion_rule')
        widgets = {'content': forms.Textarea(attrs={'rows': 8})}
        labels = {'content': 'Overview / article text', 'video_file': 'Upload video',
                  'duration_minutes': 'Duration (minutes)'}

    def clean(self):
        data = super().clean()
        if data.get('lesson_type') == Lesson.LessonType.VIDEO:
            if not data.get('video_file') and not data.get('video_url'):
                self.add_error('video_url', 'Upload a video file or provide a video URL.')
        elif not (data.get('content') or '').strip():
            self.add_error('content', 'Article lessons need some text.')
        return data


class ResourceForm(forms.ModelForm):
    class Meta:
        model = LessonResource
        fields = ('title', 'resource_type', 'file', 'url')

    def clean(self):
        data = super().clean()
        if not data.get('file') and not data.get('url'):
            raise forms.ValidationError('Upload a file or enter a link.')
        if data.get('resource_type') == LessonResource.ResourceType.LINK and not data.get('url'):
            self.add_error('url', 'External links need a URL.')
        return data


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ('title', 'description', 'lesson', 'passing_score', 'time_limit_minutes', 'max_attempts',
                  'shuffle_questions', 'result_visibility', 'show_explanations', 'is_required', 'is_published')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}
        labels = {'lesson': 'Attach to lesson', 'passing_score': 'Passing score (%)',
                  'time_limit_minutes': 'Time limit (minutes)'}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lesson'].queryset = course.lessons()
        self.fields['lesson'].empty_label = 'Course-level quiz (final assessment)'


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ('question_type', 'text', 'points', 'explanation')
        widgets = {'text': forms.Textarea(attrs={'rows': 3}), 'explanation': forms.Textarea(attrs={'rows': 2})}


class BaseOptionFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, question_type=None, **kwargs):
        self.question_type = question_type
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        options = [f.cleaned_data for f in self.forms
                   if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('text')]
        correct = sum(1 for o in options if o.get('is_correct'))
        qtype = self.question_type
        if len(options) < 2:
            raise forms.ValidationError('Provide at least two answer options.')
        if qtype == Question.QuestionType.TRUE_FALSE and len(options) != 2:
            raise forms.ValidationError('True/False questions need exactly two options.')
        if qtype in (Question.QuestionType.SINGLE, Question.QuestionType.TRUE_FALSE) and correct != 1:
            raise forms.ValidationError('Mark exactly one option as correct.')
        if qtype == Question.QuestionType.MULTIPLE and correct < 1:
            raise forms.ValidationError('Mark at least one option as correct.')


OptionFormSet = inlineformset_factory(
    Question, AnswerOption, formset=BaseOptionFormSet, fields=('text', 'is_correct'),
    extra=4, max_num=8, can_delete=True,
    labels={'text': 'Option', 'is_correct': 'Correct'})


class ModerationNoteForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}),
                           label='Note to reviewers (optional)')
