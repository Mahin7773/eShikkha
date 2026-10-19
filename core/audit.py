from .models import AuditLog


def client_ip(request):
    if request is None:
        return None
    return request.META.get('REMOTE_ADDR')


def log_action(actor, action, target=None, details=None, request=None):
    entry = AuditLog(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action,
        details=details or {},
        ip_address=client_ip(request),
    )
    if target is not None:
        entry.target_type = target._meta.model_name
        entry.target_id = str(target.pk)
        entry.target_repr = str(target)[:200]
    entry.save()
    return entry
