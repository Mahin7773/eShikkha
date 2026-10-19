from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from core.models import PlatformSettings

from . import services
from .forms import InstructorApplicationForm, LoginForm, ProfileForm, RegistrationForm


class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:post_login')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
        messages.success(request, f'Welcome to eShikkha, {user.first_name}!')
        if form.cleaned_data['wants_to_teach']:
            return redirect('accounts:apply_instructor')
        return redirect('courses:list')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def post_login(request):
    user = request.user
    if user.is_platform_admin:
        return redirect('adminpanel:dashboard')
    if user.is_instructor:
        return redirect('studio:dashboard')
    if user.enrollments.exists():
        return redirect('learning:dashboard')
    return redirect('core:home')


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # stay signed in
            messages.success(request, 'Your password has been changed.')
            return redirect('accounts:profile')
        messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'accounts/password_change.html', {'form': form})


def apply_instructor(request):
    user = request.user
    if not user.is_authenticated:  # landing page with sign-up prompt
        return render(request, 'accounts/apply_instructor.html', {
            'requires_approval': PlatformSettings.load().require_instructor_approval})
    applications = user.instructor_applications.all()
    can_apply = user.is_student and user.pending_application is None
    form = InstructorApplicationForm(request.POST or None, initial={'headline': user.headline})
    if request.method == 'POST' and can_apply:
        if form.is_valid():
            try:
                application = services.apply_for_instructor(user, form)
            except services.AccountError as exc:
                messages.error(request, str(exc))
            else:
                if application.status == application.Status.APPROVED:
                    messages.success(request, 'You are now an instructor. Create your first course!')
                    return redirect('studio:dashboard')
                messages.success(request, 'Application submitted. We will notify you once it is reviewed.')
                return redirect('accounts:apply_instructor')
        else:
            messages.error(request, 'Please correct the highlighted fields.')
    return render(request, 'accounts/apply_instructor.html', {
        'form': form, 'applications': applications, 'can_apply': can_apply,
        'requires_approval': PlatformSettings.load().require_instructor_approval,
    })


login_view = LoginView.as_view()
logout_view = auth_views.LogoutView.as_view()
