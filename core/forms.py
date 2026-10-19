from django import forms

from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ('reason', 'details')
        widgets = {'details': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us what is wrong (optional)'})}
