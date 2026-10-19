from django import forms
from django.utils.text import slugify

from core.models import Announcement, PlatformSettings
from courses.models import Category, Course, ModerationDecision, Tag
from courses.services import ADMIN_ACTIONS


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description', 'order', 'is_active')

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            base = slugify(obj.name) or 'category'
            slug, n = base, 2
            while Category.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug, n = f'{base}-{n}', n + 1
            obj.slug = slug
        if commit:
            obj.save()
        return obj


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ('name',)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Tag.objects.filter(slug=slugify(name)).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A tag with this name already exists.')
        return name

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = slugify(obj.name)
        if commit:
            obj.save()
        return obj


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ('title', 'body', 'audience', 'is_active')
        widgets = {'body': forms.Textarea(attrs={'rows': 4})}


class PlatformSettingsForm(forms.ModelForm):
    class Meta:
        model = PlatformSettings
        exclude = ('updated_at',)
        widgets = {'certificate_accent_color': forms.TextInput(attrs={'type': 'color'})}


class ModerationForm(forms.Form):
    action = forms.ChoiceField(choices=[(a, ModerationDecision.Action(a).label) for a in ADMIN_ACTIONS])
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}),
                             help_text='Required for every decision except approval. The instructor sees this.')


class ReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), max_length=500)


class GrantEnrollmentForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.filter(status=Course.Status.PUBLISHED))
    reason = forms.CharField(max_length=200, help_text='Recorded in the audit log.')
