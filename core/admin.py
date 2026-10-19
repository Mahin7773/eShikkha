from django.contrib import admin

from .models import Announcement, AuditLog, PlatformSettings, Report


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'target_type', 'target_repr', 'ip_address')
    list_filter = ('action', 'target_type')
    search_fields = ('target_repr', 'actor__username')

    def has_change_permission(self, request, obj=None):
        return False  # append-only

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PlatformSettings)
admin.site.register(Announcement)
admin.site.register(Report)
