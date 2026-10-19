from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import InstructorApplication

User = get_user_model()


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    wants_to_teach = forms.BooleanField(
        required=False, label='I want to teach on eShikkha',
        help_text='You will be asked a few questions about your teaching experience.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Username or email', max_length=254,
                               widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}))

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            # only say "suspended" when the password was right
            identifier = self.cleaned_data.get('username', '')
            field = 'email__iexact' if '@' in identifier else 'username__iexact'
            user = User.objects.filter(**{field: identifier}).first()
            if user and not user.is_active and user.check_password(self.cleaned_data.get('password', '')):
                raise forms.ValidationError(
                    'This account has been suspended. Contact support if you think this is a mistake.',
                    code='suspended')
            raise


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'headline', 'bio', 'website', 'avatar')
        widgets = {'bio': forms.Textarea(attrs={'rows': 5})}

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email


class InstructorApplicationForm(forms.ModelForm):
    class Meta:
        model = InstructorApplication
        fields = ('headline', 'expertise', 'experience', 'sample_url')
        widgets = {'experience': forms.Textarea(attrs={'rows': 5})}
        labels = {'headline': 'Professional headline', 'sample_url': 'Sample work (optional)'}
