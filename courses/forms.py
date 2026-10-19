from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(i, f'{i} star{"s" if i > 1 else ""}') for i in range(5, 0, -1)],
                                    coerce=int, widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'What did you like? What could be better?'})}
        labels = {'comment': 'Your review'}
