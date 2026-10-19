from django.db import transaction
from django.utils import timezone

from core.audit import log_action
from core.models import PlatformSettings
from notifications.models import Notification
from notifications.services import notify

from .models import InstructorApplication, User


class AccountError(Exception):
    pass


@transaction.atomic
def apply_for_instructor(user, form):
    if not user.is_student:
        raise AccountError('Only student accounts can apply to teach.')
    if user.pending_application:
        raise AccountError('You already have an application under review.')
    application = form.save(commit=False)
    application.user = user
    application.save()
    if not PlatformSettings.load().require_instructor_approval:
        decide_application(application, None, approve=True, note='Approved automatically.')
        return application
    for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
        notify(admin, f'New instructor application from {user.display_name}',
               application.expertise, url='/manage/applications/', kind=Notification.Kind.ACCOUNT)
    return application


@transaction.atomic
def decide_application(application, admin, approve, note='', request=None):
    if application.status != InstructorApplication.Status.PENDING:
        raise AccountError('This application has already been decided.')
    if not approve and not note.strip():
        raise AccountError('Please give the applicant a reason.')
    application.status = InstructorApplication.Status.APPROVED if approve else InstructorApplication.Status.REJECTED
    application.reviewed_by = admin
    application.reviewed_at = timezone.now()
    application.review_note = note
    application.save()
    user = application.user
    if approve:
        user.role = User.Role.INSTRUCTOR
        if not user.headline:
            user.headline = application.headline
        user.save(update_fields=['role', 'headline'])
        notify(user, 'Your instructor application was approved',
               'Welcome aboard! Open the instructor studio to create your first course.',
               url='/teach/', kind=Notification.Kind.ACCOUNT)
    else:
        notify(user, 'Your instructor application was not approved', note,
               url='/accounts/teach/', kind=Notification.Kind.ACCOUNT)
    if admin:
        log_action(admin, 'application.approved' if approve else 'application.rejected', application,
                   {'user': user.username, 'note': note}, request=request)
    return application


@transaction.atomic
def set_suspended(user, admin, suspend, reason='', request=None):
    if user.pk == admin.pk:
        raise AccountError('You cannot suspend your own account.')
    if user.is_superuser and not admin.is_superuser:
        raise AccountError('Only a superuser can suspend another superuser.')
    if suspend:
        if not reason.strip():
            raise AccountError('A suspension reason is required.')
        user.is_active = False
        user.suspended_at = timezone.now()
        user.suspension_reason = reason
    else:
        user.is_active = True
        user.suspended_at = None
        user.suspension_reason = ''
    user.save(update_fields=['is_active', 'suspended_at', 'suspension_reason'])
    log_action(admin, 'user.suspended' if suspend else 'user.reactivated', user, {'reason': reason}, request=request)
    return user


@transaction.atomic
def change_role(user, admin, role, request=None):
    if role not in User.Role.values:
        raise AccountError('Unknown role.')
    if user.pk == admin.pk:
        raise AccountError('You cannot change your own role.')
    if user.is_superuser:
        raise AccountError("A superuser's role cannot be changed here.")
    old = user.role
    user.role = role
    user.save(update_fields=['role'])
    log_action(admin, 'user.role_changed', user, {'from': old, 'to': role}, request=request)
