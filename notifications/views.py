from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


@login_required
def notification_list(request):
    qs = request.user.notifications.all()
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'notifications/list.html', {'page_obj': page})


@login_required
@require_POST
def open_notification(request, pk):
    notification = get_object_or_404(request.user.notifications, pk=pk)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    target = notification.url
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('notifications:list')
