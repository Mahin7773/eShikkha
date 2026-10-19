from django.conf import settings

from .models import Announcement, PlatformSettings


def platform(request):
    from courses.models import Category

    ctx = {
        'platform': PlatformSettings.load(),
        'DEBUG': settings.DEBUG,
        'nav_categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
    }
    user = getattr(request, 'user', None)
    audiences = [Announcement.Audience.ALL]
    if user is not None and user.is_authenticated:
        if user.is_instructor:
            audiences.append(Announcement.Audience.INSTRUCTORS)
        if user.is_student:
            audiences.append(Announcement.Audience.STUDENTS)
            from commerce.models import CartItem
            ctx['cart_count'] = CartItem.objects.filter(cart__user=user).count()
        ctx['unread_notifications'] = user.notifications.filter(is_read=False).count()
    else:
        audiences.append(Announcement.Audience.STUDENTS)

    session = getattr(request, 'session', None)
    dismissed = session.get('dismissed_announcements', []) if session is not None else []
    ctx['announcement'] = (Announcement.objects.filter(is_active=True, audience__in=audiences)
                           .exclude(pk__in=dismissed).first())
    return ctx
