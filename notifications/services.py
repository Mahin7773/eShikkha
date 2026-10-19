from .models import Notification


def notify(recipient, title, message='', url='', kind=Notification.Kind.INFO):
    return Notification.objects.create(recipient=recipient, title=title[:160],
                                       message=message, url=url, kind=kind)
