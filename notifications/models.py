from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        INFO = 'info', 'Information'
        ENROLLMENT = 'enrollment', 'Enrollment'
        REVIEW = 'review', 'Review'
        MODERATION = 'moderation', 'Moderation'
        PAYMENT = 'payment', 'Payment'
        CERTIFICATE = 'certificate', 'Certificate'
        ACCOUNT = 'account', 'Account'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='notifications')
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.INFO)
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'])]

    def __str__(self):
        return self.title
