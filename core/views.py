from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User
from courses import selectors
from courses.models import Category, Course, Review
from learning.models import Enrollment

from .forms import ReportForm
from .models import Announcement, Report


def home(request):
    courses = selectors.marketplace_courses()
    categories = (Category.objects.filter(is_active=True)
                  .annotate(course_count=Count('courses', filter=Q(courses__status=Course.Status.PUBLISHED)))
                  .filter(course_count__gt=0))
    return render(request, 'core/home.html', {
        'featured': courses.filter(is_featured=True).order_by('-published_at')[:4],
        'bestsellers': courses.order_by('-students_count', '-rating_avg')[:8],
        'newest': courses.order_by('-published_at')[:4],
        'top_rated': courses.filter(rating_count__gt=0).order_by('-rating_avg', '-rating_count')[:4],
        'instructors': selectors.top_instructors(),
        'categories': categories,
        'stats': {
            'courses': Course.objects.published().count(),
            'students': Enrollment.objects.values('student').distinct().count(),
            'instructors': User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True).count(),
        },
    })


_REPORT_TARGETS = {
    'course': (Course, 'course'),
    'review': (Review, 'review'),
    'user': (User, 'reported_user'),
}


@login_required
def report(request, target_type, pk):
    if target_type not in _REPORT_TARGETS:
        return redirect('core:home')
    model, field = _REPORT_TARGETS[target_type]
    target = get_object_or_404(model, pk=pk)
    back = request.GET.get('next') or request.POST.get('next') or '/'
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = '/'

    form = ReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        duplicate = Report.objects.filter(reporter=request.user, target_type=target_type,
                                          status=Report.Status.OPEN, **{field: target}).exists()
        if duplicate:
            messages.info(request, 'You have already reported this. Our moderators will review it.')
        else:
            report = form.save(commit=False)
            report.reporter = request.user
            report.target_type = target_type
            setattr(report, field, target)
            report.save()
            messages.success(request, 'Thank you. Your report has been sent to the moderators.')
        return redirect(back)
    return render(request, 'core/report.html', {'form': form, 'target': target,
                                                'target_type': target_type, 'next': back})


@require_POST
def dismiss_announcement(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    dismissed = set(request.session.get('dismissed_announcements', []))
    dismissed.add(announcement.pk)
    request.session['dismissed_announcements'] = list(dismissed)
    back = request.POST.get('next', '/')
    return redirect(back if url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}) else '/')


def page_not_found(request, exception):
    return render(request, '404.html', status=404)


def permission_denied(request, exception):
    return render(request, '403.html', status=403)


def server_error(request):
    return render(request, '500.html', status=500)
